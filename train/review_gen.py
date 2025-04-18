import torch, math, torch.nn as nn


class ReviewGen(nn.Module):
    def __init__(self, vocab_size, ctx_len=128, d_model=128, n_heads=2, n_layers=2):
        super().__init__()
        self.tok_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Parameter(torch.zeros(1, ctx_len, d_model))

        def block():
            return nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=n_heads,
                dim_feedforward=4 * d_model,
                activation="gelu",
                batch_first=True,
            )

        self.transformer = nn.TransformerEncoder(block(), num_layers=n_layers)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, idx):
        B, T = idx.shape
        x = self.tok_emb(idx) + self.pos_emb[:, :T]
        x = self.transformer(x)
        return self.lm_head(x)
