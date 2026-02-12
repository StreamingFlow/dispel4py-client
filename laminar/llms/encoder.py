import torch
from transformers import pipeline, AutoModel, AutoTokenizer


class LaminarCodeEncoder:

    def __init__(self, model_name: str = "microsoft/reacc-py-retriever"):
        self.model_text_to_code = pipeline(
            model="Lazyhope/RepoSim",
            trust_remote_code=True,
            device_map="auto")
        self.model_code_completion = AutoModel.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def encode(self, string, model_type: int = 1):
        if model_type == 1:
            with torch.no_grad():
                embedding = self.model_text_to_code.encode(string, 512)
            final_t = embedding.squeeze()

        else:
            with torch.no_grad():
                inputs = self.tokenizer(string, padding="max_length", truncation=True, max_length=512, return_tensors="pt")
                outputs = self.model_code_completion(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1)  # You can use any pooling strategy here
            final_t = embedding.squeeze()
        return final_t
