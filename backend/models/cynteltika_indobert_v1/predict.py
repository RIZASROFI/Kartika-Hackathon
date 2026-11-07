import os
import torch
import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F

class CynteltikaPredictor:
    def __init__(self, model_dir=None):
        if model_dir is None:
            # Mengarah ke folder internal di dalam paket
            model_dir = os.path.join(os.path.dirname(__file__), "model")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.to(self.device)
        self.model.eval()
        
        # Load Label Mapping
        label_map_path = os.path.join(os.path.dirname(__file__), "metadata", "label_mapping.json")
        if os.path.exists(label_map_path):
            with open(label_map_path, "r") as f:
                self.label_map_data = json.load(f)
        else:
            # Model dilatih dengan label 0 = Hoax, 1 = Fact.
            self.label_map_data = {"0": "Hoax", "1": "Fact"}

    def _probabilities(self, probs):
        """Petakan probabilitas per indeks ke nama label dari label_mapping.json."""
        return {
            self.label_map_data.get(str(index), f"class_{index}"): round(float(p), 4)
            for index, p in enumerate(probs)
        }

    def predict(self, text):
        # Penanganan input kosong atau tidak valid
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            return {
                "error": "Input teks tidak valid atau kosong",
                "predicted_label": "Unknown",
                "label_id": -1,
                "confidence": 0.0,
                "probabilities": self._probabilities([0.0, 0.0]),
                "model_version": "cynteltika_indobert_v1"
            }
            
        try:
            # Tokenisasi input
            inputs = self.tokenizer(
                text,
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )
            
            input_ids = inputs["input_ids"].to(self.device)
            attention_mask = inputs["attention_mask"].to(self.device)
            
            with torch.no_grad():
                outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
                logits = outputs.logits
                probs = F.softmax(logits, dim=1).cpu().numpy()[0]
                
            pred_id = int(torch.argmax(logits, dim=1).cpu().item())
            confidence = float(probs[pred_id])
            
            label_name = self.label_map_data.get(str(pred_id), "Unknown")
            
            return {
                "predicted_label": label_name,
                "label_id": pred_id,
                "confidence": round(confidence, 4),
                "probabilities": self._probabilities(probs),
                "model_version": "cynteltika_indobert_v1"
            }
        except Exception as e:
            return {
                "error": f"Gagal melakukan inferensi: {str(e)}",
                "predicted_label": "Unknown",
                "label_id": -1,
                "confidence": 0.0,
                "probabilities": self._probabilities([0.0, 0.0]),
                "model_version": "cynteltika_indobert_v1"
            }

if __name__ == "__main__":
    # Demo pengujian jika dijalankan langsung
    predictor = CynteltikaPredictor()
    sample_text = "Pemerintah resmi menaikkan tarif pajak mulai bulan depan."
    res = predictor.predict(sample_text)
    print(json.dumps(res, indent=4))