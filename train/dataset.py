import torch
from torch.utils.data import Dataset
import random, json, pathlib
from tokenizers import Tokenizer


class ReviewLMDataset(Dataset):
    def __init__(self, json_path, tokenizer_path, seq_len=128):
        self.seq_len = seq_len
        self.tokenizer = Tokenizer.from_file(tokenizer_path)

        with open(json_path) as f:
            raw = json.load(f)
        texts = [r["text"] for r in raw if r.get("text")]
        corpus = "\n".join(texts)

        ids = self.tokenizer.encode(corpus).ids
        if len(ids) < self.seq_len + 1:
            raise ValueError(
                f"Corpus too small: {len(ids)} tokens, need at least {self.seq_len + 1}"
            )

        n_complete_seqs = len(ids) // (self.seq_len + 1)
        self.tokens = torch.tensor(
            ids[: n_complete_seqs * (self.seq_len + 1)], dtype=torch.long
        )
        self.n_samples = n_complete_seqs

    def __len__(self):  # number of training examples
        return self.n_samples

    def __getitem__(self, idx):
        start = idx * (self.seq_len + 1)
        x = self.tokens[start : start + self.seq_len]
        y = self.tokens[start + 1 : start + self.seq_len + 1]
        return x, y
