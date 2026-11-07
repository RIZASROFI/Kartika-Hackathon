# LAPORAN FINALISASI & AUDIT MODEL INDOBERT CYNTELTIKA V1

**Tanggal Finalisasi**: 2026-11-05 02:40:36
**Status Rilis**: **DRAFT-RELEASE (Verifikasi Kross-Sumber & Bias Terbatas)**

---

## 1. Identitas Model
- **Arsitektur**: BertForSequenceClassification
- **Pretrained Base**: `indobenchmark/indobert-base-p1`
- **Jumlah Parameter**: ~110 Juta
- **Output**: 2-Kelas (Biner)

## 2. Dataset & Pembagian Data
- **Total Dataset Terintegrasi**: 27.471 baris
- **Pembagian**: 80% Train, 10% Val, 10% Test
- **Data Latih (Train)**: 974 baris
- **Data Validasi (Val)**: 209 baris
- **Data Uji (Test Set)**: 209 baris

## 3. Hasil Komparasi Eksperimen
1. **Eksperimen A (Standard CE)**: Peak Val Macro F1 = 0.9600 (Epoch 2)
2. **Eksperimen B (Weighted CE)**: Peak Val Macro F1 = 0.9811 (Epoch 2)

**Keputusan**: Checkpoint **Eksperimen B (Epoch 2)** secara formal terpilih karena memiliki loss validasi terendah (`0.0447`) dan F1 kelas minoritas tertinggi.

## 4. Hasil Pengujian Test Set Akhir
- **Accuracy Global**: 0.9904
- **Macro F1-Score**: 0.9780
- **Precision**: 0.9946
- **Recall**: 0.9630

*Catatan Penting*: Tingginya hasil ini didorong oleh bias inheren dari data latih. Model sangat optimal membedakan teks formal jurnalisme dari klaim TurnBackHoax.

## 5. Analisis Keterbatasan & Resiko Bias
- **Confounding Penerbit**: Model rentan mengalami penurunan generalisasi jika diuji pada klaim hoaks yang ditulis dengan struktur jurnalisme formal yang kaku.
- **Status Near-Duplicate**: 61 pasangan near-duplicate masih berstatus Needs Review. Resiko kebocoran minor antar-split masih tetap ada.

## 6. Contoh Cara Penggunaan Modul predict.py
```python
from predict import CynteltikaPredictor

predictor = CynteltikaPredictor()
result = predictor.predict("Teks Berita")
print(result)
```