# train_amp.py
import argparse, json, time, logging, torch, csv, os
from torch.utils.data import DataLoader
from torch.amp import autocast, GradScaler
from tqdm.auto import tqdm
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.absolute()

from dataset import ReviewLMDataset
from review_gen import ReviewGen

# -------------------- CLI --------------------
p = argparse.ArgumentParser()
p.add_argument("--json", default=str(PROJECT_ROOT / "master.json"))
p.add_argument("--tok", default=str(PROJECT_ROOT / "tokenizer.json"))
p.add_argument("--seq-len", type=int, default=128)
p.add_argument("--bs", type=int, default=48)
p.add_argument("--epochs", type=int, default=6)
p.add_argument("--lr", type=float, default=3e-4)
p.add_argument("--log-every", type=int, default=200)
p.add_argument(
    "--csv-log", default="training_metrics.csv", help="CSV file to log metrics"
)
args = p.parse_args()

# -------------------- logging --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",  # one compact line per record
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("train")

csv_path = PROJECT_ROOT / args.csv_log
csv_exists = os.path.exists(csv_path)
csv_file = open(csv_path, "a", newline="")
csv_writer = csv.writer(csv_file)
if not csv_exists:
    csv_writer.writerow(["step", "epoch", "loss", "tokens_per_sec"])

# -------------------- dataset / model --------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
ds = ReviewLMDataset(args.json, args.tok, seq_len=args.seq_len)
dl = DataLoader(ds, batch_size=args.bs, shuffle=True, pin_memory=True)

model = ReviewGen(len(ds.tokenizer.get_vocab()), ctx_len=args.seq_len).to(device)
opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-2)

scaler = GradScaler(enabled=(device == "cuda"))

tokens_per_step = args.bs * args.seq_len

# -------------------- training loop --------------------
global_step = 0
for epoch in range(args.epochs):
    epoch_start = time.time()
    running_loss = 0.0
    with tqdm(total=len(dl), desc=f"Epoch {epoch}", unit="batch") as pbar:
        for it, (x, y) in enumerate(dl):
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)

            with autocast(device_type=device, enabled=(device == "cuda")):
                logits = model(x)
                loss = torch.nn.functional.cross_entropy(
                    logits.view(-1, logits.size(-1)), y.view(-1)
                )

            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)

            running_loss += loss.item()
            global_step += 1
            pbar.update(1)

            # ---- periodic logging ----
            if global_step % args.log_every == 0:
                avg_loss = running_loss / args.log_every
                tokens_sec = (tokens_per_step * args.log_every) / (
                    time.time() - epoch_start
                )
                epoch_start = time.time()
                running_loss = 0.0

                payload = {
                    "step": global_step,
                    "epoch": epoch,
                    "loss": round(avg_loss, 4),
                    "tokens_per_sec": int(tokens_sec),
                }
                log.info(json.dumps(payload))  # ↳     single‑line JSON

                csv_writer.writerow(
                    [global_step, epoch, round(avg_loss, 4), int(tokens_sec)]
                )
                csv_file.flush()

# -------------------- teardown --------------------
csv_file.close()  # Close the CSV file
torch.save(model.state_dict(), str(PROJECT_ROOT / "review_gen.pt"))
log.info("Finished training; model saved to review_gen.pt")
log.info(f"Training metrics saved to {args.csv_log}")
