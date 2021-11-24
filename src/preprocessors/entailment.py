from copy import deepcopy
from typing import Dict
import math

from src.preprocessors.task_preprocessor import FixedChoiceTaskPreprocessor


class EntailmentPreprocessor(FixedChoiceTaskPreprocessor):
    def __init__(
            self,
            choices,
            classification_template: str,
            premise_template: str,
            hypothesis_template: str,
            question_template: str,
            context_template: str,
            num_choices,
            is_mcq: bool = False,
            choice_str: str = None,
            mcq_choice_str: str = None
    ):
        assert len(choices) == num_choices
        classification_template = (
                classification_template
                or "Premise is '{}'. Hypothesis is '{}'."
        )
        premise_template = (
                premise_template
                or "{}"
        )
        hypothesis_template = (
                hypothesis_template
                or "{}"
        )
        context_template = (
                context_template
                or "Premise is '{}'. Hypothesis is '{}'."
        )
        question_template = (
                question_template
                or "Does the premise imply the hypothesis?"
        )
        super().__init__(
            choices=choices,
            classification_template=classification_template,
            premise_template=premise_template,
            hypothesis_template=hypothesis_template,
            question_template=question_template,
            context_template=context_template,
            choice_str=choice_str,
            mcq_choice_str=mcq_choice_str,
            is_mcq=is_mcq
        )

    def _process_instance(self, data_instance, idx) -> Dict:
        return {
            "choices"   : self.choices,
            "idx"       : idx,
            "domain"    : "entailment",
            "premise"   : data_instance['premise'],
            "label"     : data_instance['label'],
            "hypothesis": data_instance['hypothesis'],
        }

    def convert_to_classification(self, processed_instance: Dict) -> Dict:
        out = deepcopy(processed_instance)
        premise = out.pop('premise')
        hypothesis = out.pop('hypothesis')
        out['input_sequence'] = self.classification_template.format(premise, hypothesis)
        return out

    def convert_to_entailment(self, processed_instance: Dict) -> Dict:
        processed_instance['premise'] = self.premise_template.format(
            processed_instance['premise']
        )

        processed_instance['hypothesis'] = self.hypothesis_template.format(
            processed_instance['hypothesis']
        )
        return processed_instance

    def convert_to_qa(self, processed_instance: Dict) -> Dict:
        out = deepcopy(processed_instance)
        premise = out.pop('premise')
        hypothesis = out.pop('hypothesis')
        out['context'] = self.context_template.format(premise, hypothesis)
        out['question'] = self.question_template.format()
        return out


@FixedChoiceTaskPreprocessor.register('three_choice_entailment')
class ThreeChoiceEntailmentPreprocessor(EntailmentPreprocessor):
    def __init__(
            self,
            choices=None,
            classification_template: str = None,
            premise_template: str = None,
            hypothesis_template: str = None,
            question_template: str = None,
            context_template: str = None,
            is_mcq: bool = False,
            choice_str: str = None,
            mcq_choice_str: str = None
    ):
        if choices is None:
            choices = ["Yes", "Maybe", "No"]

        super(ThreeChoiceEntailmentPreprocessor, self).__init__(
            choices=choices,
            classification_template=classification_template,
            premise_template=premise_template,
            hypothesis_template=hypothesis_template,
            question_template=question_template,
            context_template=context_template,
            num_choices=3,
            is_mcq=is_mcq,
            choice_str=choice_str,
            mcq_choice_str=mcq_choice_str
        )


@FixedChoiceTaskPreprocessor.register('two_choice_entailment')
class TwoChoiceEntailmentPreprocessor(EntailmentPreprocessor):
    def __init__(
            self,
            choices=None,
            classification_template: str = None,
            premise_template: str = None,
            hypothesis_template: str = None,
            question_template: str = None,
            context_template: str = None,
            is_mcq: bool = False,
            choice_str: str = None,
            mcq_choice_str: str = None
    ):
        if choices is None:
            choices = ["Yes", "No"]
        super(TwoChoiceEntailmentPreprocessor, self).__init__(
            choices=choices,
            classification_template=classification_template,
            premise_template=premise_template,
            hypothesis_template=hypothesis_template,
            question_template=question_template,
            context_template=context_template,
            num_choices=2,
            is_mcq=is_mcq,
            choice_str=choice_str,
            mcq_choice_str=mcq_choice_str

        )
