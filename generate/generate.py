import argparse, torch, sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from tokenizers import Tokenizer
from train import ReviewGen

# ---------- CLI ----------
cli = argparse.ArgumentParser()
cli.add_argument("--prompt", default="", help="Seed text")
cli.add_argument("--max_new", type=int, default=80)
cli.add_argument("--temperature", type=float, default=0.9)
cli.add_argument("--top_k", type=int, default=40)
cli.add_argument("--top_p", type=float, default=0.9)
cli.add_argument("--repetition_penalty", type=float, default=1.15)
args = cli.parse_args()

# ---------- Load model + tokenizer ----------
device = "cuda" if torch.cuda.is_available() else "cpu"
tok = Tokenizer.from_file("tokenizer.json")

model = ReviewGen(len(tok.get_vocab()))
model.load_state_dict(torch.load("review_gen.pt", map_location=device))
model.to(device).eval()


# ---------- Sampling ----------
@torch.no_grad()
def sample(prompt: str) -> str:
    ids = torch.tensor(tok.encode(prompt).ids, device=device).unsqueeze(0)

    for _ in range(args.max_new):
        logits = model(ids)[:, -1] / args.temperature

        for token_id in set(ids[0].tolist()):
            logits[:, token_id] /= args.repetition_penalty

        probs = torch.softmax(logits, dim=-1)

        # top-p sampling
        if args.top_p < 1.0:
            sorted_probs, sorted_idx = torch.sort(probs, dim=-1, descending=True)
            cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
            mask = cumulative_probs > args.top_p

            mask = torch.cat(
                [torch.zeros_like(mask[:, :1], dtype=torch.bool), mask[:, :-1]], dim=-1
            )

            sorted_probs.masked_fill_(mask, 0.0)

            probs.zero_()
            probs.scatter_(-1, sorted_idx, sorted_probs)

            if probs.sum() > 0:
                probs.div_(probs.sum(dim=-1, keepdim=True))

        # top-k sampling
        if args.top_k > 0:
            topk_probs, topk_idx = torch.topk(probs, min(args.top_k, probs.size(-1)))
            probs.zero_()
            probs.scatter_(-1, topk_idx, topk_probs)

            if probs.sum() > 0:
                probs.div_(probs.sum(dim=-1, keepdim=True))

        next_id = torch.multinomial(probs, num_samples=1)
        ids = torch.cat([ids, next_id], dim=1)

    output = tok.decode(ids[0].tolist(), skip_special_tokens=True).strip()
    # clean up common BPE artifacts
    output = (
        output.replace("Ġ", " ")
        .replace("Ċ", "\n")
        .replace("âĢ¦", "...")
        .replace("âĢĻ", "'")
    )
    if output.startswith(" "):
        output = output[1:]
    output = " ".join(output.split())
    for punct in [".", ",", "!", "?", ":", ";"]:
        output = output.replace(" " + punct, punct)
    output = output.replace("\n ", "\n")
    return output


print(sample(args.prompt))
