import torch
from tqdm import tqdm
from src.models import db_session
from src.skills.zettel import Zettel
from transformers import AutoModelForCausalLM, AutoTokenizer


model_id = "meta-llama/Llama-3.2-3B-Instruct"

class PerplexityService():
    def __init__(self) -> None:
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = "cpu"
        self.model = AutoModelForCausalLM.from_pretrained(model_id).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

    def perplexity_of_text(self, input_text: str) -> float:
        # Tokenize the prompt
        encodings = self.tokenizer(input_text, return_tensors="pt")
        input_ids = encodings.input_ids.to(self.device)

        # Create target labels (shifted by 1 to the left)
        labels = input_ids.clone()

        # Forward pass with labels
        with torch.no_grad():
            outputs = self.model(input_ids=input_ids.to(self.device), labels=labels.to(self.device))

        # The loss is already the cross entropy loss
        cross_entropy = outputs.loss.item()
        perplexity = torch.exp(torch.tensor(cross_entropy))

        # print(f"Cross Entropy Loss: {cross_entropy}")
        # print(f"Perplexity: {perplexity.item()}")
        return cross_entropy, perplexity.item()


def measure_perplexity_of_zettels():
    zettels = db_session.query(Zettel).all()
    results = []
    perplexity_service = PerplexityService()
    for zettel in tqdm(zettels, desc="Measuring perplexity"):
        cross_entropy, perplexity = perplexity_service.perplexity_of_text(zettel.content)
        results.append({
            'id': zettel.id,
            'title': zettel.title,
            'perplexity': perplexity,
            'cross_entropy': cross_entropy,
        })

    with open('zettel_perplexity.csv', 'w') as f:
        f.write("Filename,Perplexity,Cross Entropy\n")
        for result in sorted(results, key=lambda x: x['perplexity']):
            title = result['title'].replace(',', '\\,')
            f.write(f"{title},{result['perplexity']},{result['cross_entropy']}\n")
