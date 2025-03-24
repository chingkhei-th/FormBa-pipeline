import os
import json5
from huggingface_hub import InferenceClient


class NERProcessor:
    def __init__(self, config):
        self.config = config["ner"]
        self.client = InferenceClient(api_key=os.getenv("HUGGINGFACEHUB_API_TOKEN"))
        self.prompt_templates = self._load_prompt_templates(config["doc_types"])

    def _load_prompt_templates(self, doc_types_config):
        templates = {}
        for doc_type, config in doc_types_config.items():
            with open(config["prompt"], "r") as f:
                templates[doc_type] = f.read().strip()
        return templates

    def extract_entities(self, text, doc_type):
        try:
            prompt_template = self.prompt_templates[doc_type]
            system_prompt = prompt_template.format(text=text)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ""},
            ]

            stream = self.client.chat.completions.create(
                model=self.config["llm_model"],
                messages=messages,
                temperature=self.config["temperature"],
                max_tokens=self.config["max_new_tokens"],
                stream=True,
            )

            output_text = self._collect_stream_output(stream)
            return self._parse_output(output_text)

        except Exception as e:
            return {"error": str(e)}

    def _collect_stream_output(self, stream):
        output_text = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                output_text += chunk.choices[0].delta.content
        return output_text

    def _parse_output(self, output_text):
        try:
            # Find first { and last } to capture the JSON block
            start = output_text.find('{')
            end = output_text.rfind('}') + 1
            json_str = output_text[start:end]

            # Remove any markdown code blocks and whitespace
            json_str = json_str.replace('```json', '').replace('```', '').strip()

            # Use JSON5 parser which is more lenient
            return json5.loads(json_str)

        except Exception as e:
            return {
                "error": f"JSON parsing failed: {str(e)}",
                "raw_output": output_text
            }
