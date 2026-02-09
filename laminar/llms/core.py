class LLMConnector:

    def _get_description_prompt(self, component_name, component_type, code):
        return self.DESCRIPTION_PROMPT.format(component_name, component_type, code)

    def __init__(self):
        self.DESCRIPTION_PROMPT = """
You are documenting dispel4py components for semantic search and retrieval.

Component name: {}
Component type: {}

Write a short, structured description that:
- Explicitly states whether this is a Processing Element (PE) or a workflow.
- Clearly describes its role in a data-processing pipeline.
- Mentions expected inputs and outputs.
- Uses consistent technical vocabulary (e.g. filtering, transformation, signal processing, orchestration).
- Mentions important parameters or configuration options if obvious from the code.

The description should be suitable for:
- semantic similarity search
- explaining results to users

Return JSON only, describing the code, the inputs and the outputs:
{{
  "description": "...",
  "inputs": ["...", ...],
  "outputs": ["...", ...]
}}

CODE:
{}
        """

    def describe(self, component_name: str, kind: str, code: str) -> dict[str, str]:
        pass
