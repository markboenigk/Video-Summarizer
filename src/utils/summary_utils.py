import logging
import re
from typing import List, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, validator

from utils.aws_utils import get_json_from_s3, save_summary_to_s3_and_dynamo

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class TechContentSummary(BaseModel):
    """
    Pydantic model for technology-type summary output.
    Validates structure of the summary field to contain 4 expected lines.
    """
    type: Literal["technology"] = Field(default="technology")
    title: str
    summary: str
    tags: List[str]
    summaries: List[dict] = Field(default_factory=list)
    companies: List[dict] = Field(default_factory=list)

    @validator("summary")
    def validate_summary_structure(cls, v: str) -> str:
        """Ensure the summary has exactly 4 labeled lines."""
        required_sections = [
            r"^Topic: .+",
            r"^Tech: .+",
            r"^Insight: .+",
            r"^Takeaway: .+"
        ]
        lines = v.strip().split("\n")
        if len(lines) != 4:
            raise ValueError("Summary must contain exactly 4 lines with labeled sections.")
        for pattern, line in zip(required_sections, lines):
            if not re.match(pattern, line):
                raise ValueError(f"Line '{line}' does not match the required pattern '{pattern}'")
        return v


class SummarySection(BaseModel):
    """Model for a section of a company summary."""
    company_name: str
    location: str
    industry: str
    funding: str
    notes: str


class StructuredOutputCompanies(BaseModel):
    """Pydantic model for summaries related to companies."""
    type: Literal["companies"]
    summaries: List[SummarySection]
    tags: List[str]
    companies: List[str]


class EmptyItem(BaseModel):
    """Placeholder model for empty sections in generic summaries."""
    pass


class GeneralOutput(BaseModel):
    """Generic summary model for non-technology, non-company transcripts."""
    type: Literal["general"]
    summaries: List[EmptyItem] = Field(default_factory=list)
    companies: List[EmptyItem] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    title: str
    summary: str


def is_summarized(record: dict) -> bool:
    """
    Check if the given record has already been summarized.

    Args:
        record (dict): DynamoDB record.

    Returns:
        bool: True if 'is_summarized' is True, else False.
    """
    return record.get("is_summarized", False)


def generate_summary(system_prompt: str, transcription_text: str, api_key: str) -> GeneralOutput:
    """
    Use OpenAI to generate a general summary.

    Args:
        system_prompt (str): Prompt for the assistant.
        transcription_text (str): Input text from transcription.
        api_key (str): OpenAI API key.

    Returns:
        GeneralOutput: Parsed output object.
    """
    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcription_text},
        ],
        text_format=GeneralOutput,
    )
    parsed_output = response.output_parsed
    parsed_output.summaries = parsed_output.summaries or []
    parsed_output.tags = parsed_output.tags or []
    parsed_output.companies = parsed_output.companies or []
    return parsed_output


def generate_company_summary(system_prompt: str, transcription_text: str, api_key: str) -> StructuredOutputCompanies:
    """
    Use OpenAI to generate a structured company summary.

    Args:
        system_prompt (str): Prompt for the assistant.
        transcription_text (str): Input text from transcription.
        api_key (str): OpenAI API key.

    Returns:
        StructuredOutputCompanies: Parsed output object.
    """
    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcription_text},
        ],
        text_format=StructuredOutputCompanies,
    )
    parsed_output = response.output_parsed
    parsed_output.summaries = parsed_output.summaries or []
    parsed_output.tags = parsed_output.tags or []
    parsed_output.companies = parsed_output.companies or []
    return parsed_output


def classify_transcription(system_prompt: str, transcription_text: str, api_key: str) -> str:
    """
    Classify transcription type (e.g., 'technology', 'companies') using OpenAI.

    Args:
        system_prompt (str): Classification prompt.
        transcription_text (str): Full transcript text.
        api_key (str): OpenAI API key.

    Returns:
        str: Classification label.
    """
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": transcription_text},
        ],
    )
    return response.output_text


def get_summary(
    config_dict: dict,
    record: dict,
    transcription_with_caption: str,
    api_key: str
) -> dict:
    """
    Generate or retrieve a summary for a transcription.

    Args:
        config_dict (dict): Configuration with S3 and Dynamo info.
        record (dict): Existing record (may contain prior summary).
        transcription_with_caption (str): Transcript with appended caption.
        api_key (str): OpenAI API key.

    Returns:
        dict: Summary JSON.
    """
    summarized_record = record if record and is_summarized(record) else None
    transcribed_record = record if record and is_summarized(record) else None
    logger.info(f"Summarized record from DynamoDB: {summarized_record}")

    if summarized_record is None:
        logger.info("Video has not been summarized - generating summary")

        transcription_text = (
            transcription_with_caption if transcribed_record is None
            else get_json_from_s3(transcribed_record['transcription_s3_key'])['text']
        )
        transcription_with_caption = transcription_text + ' Caption: ' + record.get('caption', '')

        with open('prompts/summary_prompt.txt', "r", encoding="utf-8") as f:
            system_prompt = f.read()
        with open('prompts/classification_prompt.txt', "r", encoding="utf-8") as f:
            classification_prompt = f.read()

        transcription_class = classify_transcription(classification_prompt, transcription_text, api_key)
        logger.info(f"Transcription classification: {transcription_class}")

        if transcription_class == 'companies':
            with open('prompts/company_summary_prompt.txt', "r", encoding="utf-8") as f:
                company_summary_prompt = f.read()
            summary_output = generate_company_summary(company_summary_prompt, transcription_with_caption, api_key)

        elif transcription_class == 'technology':
            with open('prompts/technology_summary_prompt.txt', "r", encoding="utf-8") as f:
                tech_summary_prompt = f.read()
            summary_output = generate_summary(tech_summary_prompt, transcription_with_caption, api_key)

        else:
            summary_output = generate_summary(system_prompt, transcription_with_caption, api_key)

        save_summary_to_s3_and_dynamo(
            config_dict['bucket_name'],
            config_dict['chat_id'],
            config_dict['videocode'],
            summary_output,
            config_dict['dynamo_table']
        )

        logger.info("Generated Summary")
        summary_json = summary_output.dict()

    else:
        logger.info("Video already summarized - fetching summary from DynamoDB")
        summary_json = get_json_from_s3(summarized_record['summary_s3_key'])

    return summary_json
