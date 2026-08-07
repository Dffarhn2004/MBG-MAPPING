# Dashboard Prioritas MBG

Dashboard decision-first untuk prioritas wilayah MBG dan early warning.

## Live dashboard (opsional)

Jika tidak ingin menjalankan secara lokal, dashboard yang sudah di-deploy bisa dibuka langsung di:

**https://mbg-priority-map.streamlit.app/**

Cukup buka link di browser — tidak perlu install Python atau dependency.

---

## Cara menjalankan (lokal)

### Prasyarat

- Python **3.11+**
- `pip` (biasanya ikut terpasang bersama Python)

### Langkah

1. Masuk ke folder project:

```bash
cd main-dashboard
```

2. (Disarankan) buat virtual environment:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Build data analisis (opsional jika file di `data/` sudah tersedia):

```bash
python data/build_analysis.py
```

Script ini menghasilkan antara lain:

- `data/analysis_ready.csv`
- `data/analysis_meta.json`
- `data/sensitivity_ranks.csv`

> Jika file-file di atas sudah ada (misalnya sudah di-commit), langkah ini bisa dilewati.

5. Jalankan dashboard Streamlit:

```bash
streamlit run app.py
```

Atau:

```bash
python -m streamlit run app.py
```

6. Buka browser ke alamat yang ditampilkan di terminal, biasanya:

`http://localhost:8501`

### Ringkasan perintah

```bash
cd main-dashboard
pip install -r requirements.txt
python data/build_analysis.py   # opsional jika data sudah ready
streamlit run app.py
```

---

## Deploy Streamlit Community Cloud

1. Push repo ke GitHub.
2. Di [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set:
   - **Main file path:** `main-dashboard/app.py` (atau `app.py` jika root repo adalah folder ini)
   - **Python version:** 3.11+
4. Pastikan data mentah/hasil analisis tersedia:
   - Commit hasil `main-dashboard/data/analysis_ready.csv`, `analysis_meta.json`, `sensitivity_ranks.csv`, **atau**
   - Jalankan `build_analysis.py` via pre-build / secrets sesuai setup cloud.

Rekomendasi deploy: commit file di `main-dashboard/data/` (hasil build) agar app langsung jalan tanpa rebuild saat cold start.
