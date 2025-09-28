# 🧪 Notebooks — Model Experiments

This folder contains lightweight, self-contained **experiment notebooks** for the Kaggle competition **“Natural Language Processing with Disaster Tweets.”**
Use these to quickly try ideas (tokenization tweaks, training schedules, different backbones) before promoting the best runs into the main pipeline.

## Contents

* **`DistilBERT.ipynb`** — baseline notebook:

  * Loads `train.csv` / `test.csv`
  * Light tweet normalization (mask URLs/@users)
  * Fine-tunes a pretrained model with 🤗 Transformers `Trainer`
  * Early stopping + restore best checkpoint
  * Threshold tuning on validation F1
  * Saves `submission.csv`

> Convention: one notebook per backbone, e.g. `DeBERTaV3Small.ipynb`, `TwitterRoBERTa.ipynb`, `RoBERTaBase.ipynb`.

---

## How to Run

1. **Install dependencies**

   ```bash
   pip install -U "transformers>=4.44" "datasets>=2.20" "accelerate>=0.34" scikit-learn
   ```
2. **Enable GPU** (Colab/Kaggle/your machine).
3. **Set dataset paths** for `train.csv` and `test.csv` in the first cell.
4. **Run all cells** → `submission.csv` will be created in the working directory.

---

## Evaluation Checklist

* **Validation F1** (primary), plus accuracy and confusion matrix.
* **Learning curves** (watch for overfit; early stopping should kick in).
* **Threshold tuning** (don’t default to 0.5; sweep and pick the best for F1).

---

## Recommended Next Steps

### Strong Backbone Contenders (often beat DistilBERT)

Swap `MODEL_NAME` and re-run, keeping everything else identical first:

* `microsoft/deberta-v3-small` — great accuracy/size tradeoff
* `microsoft/deberta-v3-base` — stronger, needs more VRAM
* `roberta-base` — solid general baseline
* `roberta-large` — heavier but strong

### Tweet-Specialized Models

* `cardiffnlp/twitter-roberta-base`
* `vinai/bertweet-base`

### Training Tweaks (Drop-in)

* **Early stopping** (already enabled):
  `evaluation_strategy="epoch"`, `metric_for_best_model="f1"`, `load_best_model_at_end=True`
* **Label smoothing**: add `label_smoothing_factor=0.05` to `TrainingArguments`
* **Epochs/LR**: try `epochs=5`, `lr=1e-5` (with early stopping)
* **Max length sweep**: 96 / 128 / 160
* **Threshold tuning**: sweep 0.2–0.8 on validation probs; use the best for test
* **Use extra columns**: prepend `keyword` and `location` to the text string

### Validation Improvements

* **5-fold Stratified CV** with out-of-fold (OOF) predictions

  * Tune a **single** decision threshold on OOF probs
  * Optional **seed averaging** (e.g., 3 runs) for stability

### Cheap Ensembles

* **Blend** a strong transformer (e.g., DeBERTa-V3-Small) with a **TF-IDF + Logistic Regression** model (probability average)
* **Seed blending**: average predictions from 2–3 seeds of the same backbone

---

## Suggested Notebook Roadmap

* `DeBERTaV3Small.ipynb` (baseline swap)
* `RoBERTaBase.ipynb` (baseline swap)
* `TwitterRoBERTa.ipynb` (tweet-specialized)
* `DistilBERT_label_smoothing.ipynb` (ε=0.05 + threshold tuning)
* `DeBERTaV3Small_5fold.ipynb` (OOF + tuned threshold)
* `Ensemble_Transformer_TFIDF.ipynb` (blend transformer with TF-IDF+LR)

---