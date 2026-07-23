# Dashboard Prioritas MBG

## Setup lokal

```bash
cd main-dashboard
pip install -r requirements.txt
python data/build_analysis.py
streamlit run app.py
```

## Deploy Streamlit Community Cloud

1. Push repo ke GitHub.
2. Di [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set:
   - **Main file path:** `main-dashboard/app.py`
   - **Python version:** 3.11+
4. Pastikan `program-cleaning/output/*.csv` ikut ter-commit, lalu jalankan `build_analysis.py` di cloud:
   - Tambahkan di Streamlit secrets atau pre-build, **atau**
   - Commit hasil `main-dashboard/data/analysis_ready.csv`, `analysis_meta.json`, `sensitivity_ranks.csv`.

Rekomendasi deploy: commit file di `main-dashboard/data/` (hasil build) agar app langsung jalan tanpa rebuild saat cold start.
