from tokenizers import Tokenizer, trainers, models, pre_tokenizers, normalizers
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.absolute()

corpus_file = str(PROJECT_ROOT / "reviews.txt")
VOCAB_SIZE = 8000
tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
tokenizer.normalizer = normalizers.Sequence(
    [
        normalizers.NFD(),  # decompose accents
        normalizers.StripAccents(),  # remove accents
        normalizers.Lowercase(),
    ]
)
tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=True)
trainer = trainers.BpeTrainer(
    vocab_size=VOCAB_SIZE, special_tokens=["[UNK]", "<pad>", "<bos>", "<eos>"]
)
tokenizer.train([corpus_file], trainer)
tokenizer.save(str(PROJECT_ROOT / "tokenizer.json"))
print("Saved tokenizer with", len(tokenizer.get_vocab()), "tokens")
