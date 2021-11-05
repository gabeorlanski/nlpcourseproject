import logging
from collections import Counter, defaultdict
from typing import Dict

import numpy as np
from tqdm import tqdm
import torch
from t5.data.glue_utils import get_glue_metric, get_super_glue_metric
from t5.evaluation import metrics as mt
import json
from transformers import T5ForConditionalGeneration

logger = logging.getLogger(__name__)

# Dictionary for storing metrics so that we can easily get them from the
# prompt templates
METRICS_DICT = {
    "BLEU"                : mt.bleu,
    "ROUGE"               : mt.rouge,
    "Span Squad"          : mt.span_squad,
    "Squad"               : mt.squad,
    "Trivia QA"           : mt.trivia_qa,
    "Accuracy"            : mt.accuracy,
    "Sequence Accuracy"   : mt.sequence_accuracy,
    "Pearson Correlation" : mt.pearson_corrcoef,
    "Spearman Correlation": mt.spearman_corrcoef,
    "MultiRC"             : mt.multirc_f1_over_all_answers,
    "AUC"                 : mt.auc,
    "COQA F1"             : mt.coqa_f1,
    "Edit Distance"       : mt.edit_distance,
    "Other"               : mt.accuracy,
}


def evaluate(
        task,
        out_path,
        data_loader,
        model_name,
        tokenizer,
        metrics,
        max_gen_len,
        generator_kwargs: Dict = None
):
    # Want to always have accuracy, so add it to the metrics if it is not
    # already present.
    if "Accuracy" not in metrics:
        metrics.append("Accuracy")

    model = T5ForConditionalGeneration.from_pretrained(model_name).to(torch.device(0))
    logger.info(f"Starting Generation")
    pred_path = out_path.joinpath('predictions.jsonl')
    pred_file = pred_path.open('w', encoding="utf-8")
    batches_seen = 0

    # Create a metric tracker for keeping track of metrics we use.
    metric_tracker = Counter()
    description = ""
    for name, value in metric_tracker.items():
        description += f"{name}: {0.0:.3f} "

    data_iterator = tqdm(data_loader, desc=description)
    for batch in data_iterator:
        logger.debug(f"Got batch with shape {batch['input_ids'].shape}")
        generated = model.generate(
            input_ids=batch['input_ids'].to(torch.device(0)),
            attention_mask=batch['attention_mask'].to(torch.device(0)),
            max_length=min(max_gen_len, 16),
            early_stopping=True,
            **(generator_kwargs or {})
        )

        source = tokenizer.batch_decode(batch['input_ids'], skip_special_tokens=True)
        gold = tokenizer.batch_decode(batch['labels'], skip_special_tokens=True)

        # Convert preds to a list of lists where each list only has a single
        # element so that we only need to handle the case where there are
        # multiple beams.
        generated = generated.reshape(
            (len(gold), generator_kwargs.get('num_return_sequences', 1), -1))
        logger.debug(f"Calculating metrics {metrics}")

        # Pre initialize the preds nested array here because it saves time
        # later. Faster then appending.
        preds = [[None for _ in range(generated.shape[1])] for _ in range(len(gold))]
        for m in metrics:

            # Calculate Oracle and actual
            batch_metrics = {}
            for beam_num in range(generated.shape[1]):
                # Decode only this beam
                decoded_beams = tokenizer.batch_decode(
                    generated[:, beam_num, :],
                    skip_special_tokens=True
                )
                beam_metrics = METRICS_DICT[m](gold, decoded_beams)
                for i, seq in enumerate(decoded_beams):
                    preds[i][beam_num] = seq

                for metric, value in beam_metrics.items():
                    # For the actual metric, we  only care about the first beam.
                    if beam_num == 0:
                        batch_metrics[metric] = value

                    # Calculate the oracle metric and save it. Use default
                    # value of -1 if it has not been set yet.
                    batch_metrics[f"oracle_{metric}"] = max(
                        value, batch_metrics.get(f"oracle_{metric}", -1)
                    )
            logger.debug(f"Metrics for batch {batches_seen}:")
            for k, v in batch_metrics.items():
                # nice formatting, has no other effect.
                met_name = f"{k}:"
                logger.debug(f"{met_name:>20} {v:.3f}")

            for k, v in batch_metrics.items():
                metric_tracker[k] += v

        logger.debug("Saving JSON lines")
        for i, pred in enumerate(preds):
            pred_file.write(
                json.dumps({
                    "prediction": pred,
                    "target"    : gold[i],
                    "input"     : source[i]
                }) + '\n'
            )
        batches_seen += 1
        description = ""
        for name, value in metric_tracker.items():
            description += f"{name}: {value / batches_seen:.3f} "
        data_iterator.set_description(
            description,
            refresh=True
        )
    data_iterator.close()

    logger.info(f"Final scores for {task}:")
    final_metrics = {}
    for k, v in metric_tracker.items():
        final_metrics[k] = v / batches_seen

        # nice formatting, has no other effect.
        met_name = f"{k}:"
        logger.info(f"{met_name:>20} {final_metrics[k]:.3f}")

    pred_file.close()

    logger.info("Finished evaluating the dataset with the prompt.")

    metrics_file = out_path.joinpath("metrics.json")
    logger.info(f"Saving metrics to '{metrics_file}'")
    with metrics_file.open('w', encoding='utf-8') as fp:
        fp.write(json.dumps(final_metrics, indent=True))

    # Sanity check
    logger.info("Doing sanity check.")
    targets = []
    predictions = []
    m_trackers = defaultdict(list)
    pred_dicts = map(lambda l: json.loads(l), pred_path.read_text('utf-8').splitlines(False))
    for line in pred_dicts:
        targets.append(line['target'])
        predictions.append(line['prediction'][0])

        targets_mul = [line['target']] * len(line['prediction'])
        for m in metrics:
            oracle = {}
            for x, y in zip(targets_mul, line['prediction']):
                for k, v in METRICS_DICT[m]([x], [y]).items():
                    oracle[k] = max(oracle.get(k, -1), v)
            for k, v in oracle.items():
                m_trackers[k].append(v)

    logger.info("Sanity Metrics:")
    for m in metrics:
        for k, v in METRICS_DICT[m](targets, predictions).items():
            met_name = f"{k}:"
            logger.info(f"{met_name:>20} {v:.3f}")

            met_name = f"oracle_{k}:"
            logger.info(f"{met_name:>20} {np.mean(m_trackers[k]):.3f}")

    return pred_path
