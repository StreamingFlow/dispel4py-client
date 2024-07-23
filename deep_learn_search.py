import warnings

# Suppress specific warning messages
warnings.filterwarnings("ignore", message="the imp module is deprecated", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="Consider setting GitHub token to avoid hitting rate limits.")
warnings.filterwarnings("ignore", message="Some weights of RobertaModel were not initialized from the model checkpoint")

from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pandas as pd
import torch
import cloudpickle as pickle
import codecs
from transformers import pipeline, AutoModel, AutoTokenizer
from transformers import RobertaTokenizer, T5ForConditionalGeneration
from transformers import logging
logging.disable_default_handler()

model_text_to_code = pipeline(
    model="Lazyhope/RepoSim",
    trust_remote_code=True,
    device_map="auto")

model_name = "microsoft/reacc-py-retriever"
model_code_completion = AutoModel.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)


# ENCODE
def encode(string, model_type):
    if model_type == 1:
        with torch.no_grad():
            embedding = model_text_to_code.encode(string, 512)
        final_t = embedding.squeeze()

    else:
        with torch.no_grad():
            inputs = tokenizer(string, padding="max_length", truncation=True, max_length=512, return_tensors="pt")
            outputs = model_code_completion(**inputs)
            embedding = outputs.last_hidden_state.mean(dim=1)  # You can use any pooling strategy here
        final_t = embedding.squeeze()
    return final_t


# CODE SUMMARIZATION
tokenizer = RobertaTokenizer.from_pretrained('Salesforce/codet5-base-multi-sum')
summary_model = T5ForConditionalGeneration.from_pretrained('Salesforce/codet5-base-multi-sum')


def generate_summary(text):
    input_ids = tokenizer.encode(text, return_tensors="pt")
    generated_ids = summary_model.generate(input_ids, max_length=20)
    summary = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
    return summary


# SEARCH
def similarity_search(user_query, all_pes, type):
    print(f"Performing similarity search with query type: {type}")

    # format all PEs response
    all_pes_df = pd.json_normalize(all_pes)

    if type == "text":
        print("Encoding query as text...")
        # query embedding
        user_query_docs_emb = encode(user_query, 1)

        user_query_emb = user_query_docs_emb.cpu().numpy()

        embed_type = 'descEmbedding'
    else:
        print("Encoding query as code...")
        # query embedding
        user_query_docs_emb = encode(user_query, 2)

        user_query_emb = user_query_docs_emb.cpu().numpy()

        embed_type = 'codeEmbedding'

    # Compute cosine similarity
    all_pes_df[embed_type] = all_pes_df[embed_type].apply(lambda x: np.array(list(map(float, x[1:-1].split()))))

    cos_similarities = cosine_similarity(user_query_emb.reshape(1, -1), np.vstack(all_pes_df[embed_type]))

    # Add cosine similarity scores as a new column
    all_pes_df_copy = all_pes_df.copy()
    all_pes_df_copy["cosine_similarity"] = cos_similarities[0]

    # Sort the dataframe based on cosine similarity
    sorted_df = all_pes_df_copy.sort_values(by="cosine_similarity", ascending=False)

    # Retrieve the top 5 most similar documents
    top_5_similar_docs = sorted_df.head(5)

    selected_columns = ['peId', 'peName', 'description', 'cosine_similarity']
    print(top_5_similar_docs[selected_columns])

    # Retrieve code column
    obj_list = top_5_similar_docs["peCode"].apply(lambda x: pickle.loads(codecs.decode(x.encode(), "base64"))).tolist()

    return obj_list

