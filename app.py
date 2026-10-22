import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Simulator AAS SensAA: Gangguan Ca", page_icon="🔬", layout="wide")
HERE = Path(__file__).parent
_v = tuple(int(x) for x in st.__version__.split(".")[:2])
W = {"width": "stretch"} if _v >= (1, 50) else {"use_container_width": True}
SUB = {"SO4": "SO₄²⁻", "PO4": "PO₄³⁻", "Sr": "Sr²⁺", "La": "La³⁺", "EDTA": "EDTA"}
IONS = list(SUB)

# ---------------- data awal (contoh dari buku catatan) ----------------
def default_prep():
    return pd.DataFrame({
        "Nama larutan": ["Ca", "SO₄²⁻", "PO₄³⁻", "La³⁺", "Sr²⁺", "EDTA"],
        "Konsentrasi": [1000, 5000, 5000, 0.5, 0.5, 0.5],
        "Satuan": ["mg/L", "mg/L", "mg/L", "%", "%", "%"],
        "Bahan kimia": ["CaCO₃", "(NH₄)₂SO₄", "(NH₄)₂HPO₄", "LaCl₃", "SrCl₂", "EDTA"],
        "Bobot (g)": [0.25, 0.6878, 0.6953, 0.4417, 0.9046, 0.5705],
        "Volume labu (mL)": [100.0] * 6,
        "Mr analit": [40.078, 96.06, 94.97, 138.905, 87.62, np.nan],
        "Mr bahan": [100.087, 132.14, 132.06, 245.26, 158.53, np.nan],
    })

def default_std():
    return pd.DataFrame({
        "Konsentrasi kerja Ca (mg/L)": [0.0, 1.0, 2.0, 3.0, 4.0],
        "V larutan baku (mL)": [0.0, 0.5, 1.0, 1.5, 2.0],
        "V labu takar (mL)": [100.0] * 5,
        "Abs": [-0.012, 0.049, 0.096, 0.155, 0.211],
    })

def default_trt():
    n = np.nan
    rows = [(2, n, n, n, n, n, .113), (2, 100, n, n, n, n, .051), (2, 100, n, 100, n, n, .118),
            (2, 100, n, n, 100, n, .110), (2, 100, n, n, n, 100, .0834), (2, n, 100, n, n, n, .033),
            (2, n, 100, 100, n, n, .040), (2, n, 100, n, 100, n, .050), (2, n, 100, n, n, 100, .034)]
    return pd.DataFrame(rows, columns=["Ca"] + IONS + ["A1"])

ss = st.session_state
def reset_all():
    ss.ver = ss.get("ver", 0) + 1
    ss.prep_df, ss.std_df = default_prep(), default_std()
    ss.trt_df = ss.trt_last = default_trt()
    ss.n_applied = 1
    ss.n_in = 1
if "prep_df" not in ss:
    ss.ver = 0
    reset_all()

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Pengaturan")
    rmin, rmax = st.slider("Batas % recovery", 50, 150, (85, 115))
    rsd_max = st.number_input("Batas % RSD (kurang dari)", 0.5, 20.0, 5.0, 0.5)
    stock = st.number_input("Konsentrasi larutan baku Ca (mg/L)", 1.0, 100000.0, 100.0, 10.0,
                            help="Dipakai untuk memeriksa volume pipet pada deret standar.")
    st.button("Muat ulang data buku catatan", on_click=reset_all)
    st.caption("Data awal adalah contoh dari buku catatan. Ganti dengan data pengukuran Anda.")

st.title("AAS GBC SensAA: analisis gangguan kalsium pada SSA nyala")
st.caption("Model 3D interaktif, simulasi cara kerja, dan perhitungan gangguan anion pada penetapan Ca.")
tab_sim, tab_theory, tab_calc, tab_ref = st.tabs(
    ["🔬 Instrumen 3D dan simulasi", "📖 Prinsip dan gangguan Ca", "🧮 Perhitungan", "📚 Referensi"])

# ---------------- perhitungan (dijalankan dulu agar data tersedia untuk simulasi 3D) ----------------
def f(x, d=3):
    return "-" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}".replace(".", ",")

with tab_calc:
    st.subheader("1. Pembuatan larutan")
    st.caption("Baris bisa ditambah lewat baris kosong di bawah tabel. Mr boleh dikosongkan.")
    prep = st.data_editor(
        ss.prep_df, num_rows="dynamic", **W, hide_index=True, key=f"prep_{ss.ver}",
        column_config={"Satuan": st.column_config.SelectboxColumn(options=["mg/L", "%"], required=True)})
    p = prep.copy()
    mult = np.where(p["Satuan"] == "%", 10000.0, 1.0)
    p["Bobot teoritis (g)"] = p["Konsentrasi"] * mult * p["Volume labu (mL)"] / 1e6 * p["Mr bahan"] / p["Mr analit"]
    p["Selisih (%)"] = (p["Bobot (g)"] - p["Bobot teoritis (g)"]) / p["Bobot teoritis (g)"] * 100
    chk = p.dropna(subset=["Selisih (%)"])
    for _, r in chk[chk["Selisih (%)"].abs() > 5].iterrows():
        st.warning(f"{r['Nama larutan']}: bobot {f(r['Bobot (g)'], 4)} g berbeda {f(r['Selisih (%)'], 1)}% dari teoritis "
                   f"{f(r['Bobot teoritis (g)'], 4)} g. Periksa data atau Mr.")
    if len(chk):
        st.dataframe(p[["Nama larutan", "Bobot (g)", "Bobot teoritis (g)", "Selisih (%)"]].round(4),
                     hide_index=True, **W)

    st.subheader("2. Pembuatan dan pengukuran deret standar")
    std = st.data_editor(
        ss.std_df, num_rows="dynamic", **W, hide_index=True, key=f"std_{ss.ver}",
        column_config={"Abs": st.column_config.NumberColumn(format="%.4f")})
    cx, cv, cvf, ca = std.columns
    for i, r in std.reset_index(drop=True).iterrows():
        cd = r[cv] * stock / r[cvf]
        if np.isfinite(cd) and np.isfinite(r[cx]) and abs(cd - r[cx]) > max(.02 * r[cx], .01):
            st.warning(f"Baris {i+1}: {f(r[cv],2)} mL × {f(stock,1)} mg/L ÷ {f(r[cvf],0)} mL = {f(cd,3)} mg/L, "
                       f"tetapi konsentrasi kerja tercatat {f(r[cx],2)} mg/L. Periksa konsentrasi larutan baku atau volume pipet.")
    d = std.dropna(subset=[cx, ca])
    fitres = None
    if len(d) >= 3 and np.ptp(d[cx]) > 0:
        x, y = d[cx].to_numpy(float), d[ca].to_numpy(float)
        m, b = np.polyfit(x, y, 1)
        r_ = np.corrcoef(x, y)[0, 1]
        syx = float(np.sqrt(((y - (m * x + b)) ** 2).sum() / (len(x) - 2)))
        fitres = (m, b)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Koefisien korelasi (r)", f(r_, 4)); c2.metric("Slope (b)", f(m, 4))
        c3.metric("Intercept (a)", f(b, 4)); c4.metric("r²", f(r_ ** 2, 4))
        pts = pd.DataFrame({"C": x, "A": y})
        ln = pd.DataFrame({"C": [x.min(), x.max()]}).assign(A=lambda t: m * t.C + b)
        st.altair_chart(
            alt.Chart(pts).mark_circle(size=90, color="#c2410c").encode(
                x=alt.X("C", title="Konsentrasi Ca (mg/L)"), y=alt.Y("A", title="Absorbansi"))
            + alt.Chart(ln).mark_line(color="#2c4a5e").encode(x="C", y="A"), **W)
        st.caption(f"Persamaan: A = {f(m,4)}·C {'-' if b < 0 else '+'} {f(abs(b),4)}")
    else:
        st.info("Isi minimal 3 titik standar untuk membuat kurva kalibrasi.")

    st.subheader("3. Pengukuran Ca dengan pengganggu")
    n = st.number_input("Jumlah ulangan absorbansi (tidak dibatasi)", 1, 30, step=1, key="n_in")
    if n != ss.n_applied:
        base = ss.trt_last.copy().reset_index(drop=True)
        for k in range(1, n + 1):
            if f"A{k}" not in base:
                base[f"A{k}"] = np.nan
        base = base[["Ca"] + IONS + [f"A{k}" for k in range(1, n + 1)]]
        ss.trt_df, ss.n_applied = base, n
    cfg = {"Ca": st.column_config.NumberColumn("Ca (mg/L)", min_value=0)}
    cfg.update({k: st.column_config.NumberColumn(f"{SUB[k]} (mg/L)", min_value=0) for k in IONS})
    cfg.update({f"A{k}": st.column_config.NumberColumn(f"Abs {k}", format="%.4f") for k in range(1, n + 1)})
    trt = st.data_editor(ss.trt_df, num_rows="dynamic", **W, hide_index=True,
                         key=f"trt_{ss.ver}_{n}", column_config=cfg)
    ss.trt_last = trt.reset_index(drop=True)

    acols = [c for c in trt.columns if c.startswith("A")]
    out = []
    for i, r in trt.reset_index(drop=True).iterrows():
        parts = ["Ca"] + [SUB[k] for k in IONS if pd.notna(r[k]) and r[k] > 0]
        ab = [float(r[c]) for c in acols if pd.notna(r[c])]
        mean_c = sd = rsd = rec = np.nan
        if fitres and ab:
            conc = [(a - fitres[1]) / fitres[0] for a in ab]
            mean_c = float(np.mean(conc))
            sd = float(np.std(conc, ddof=1)) if len(conc) > 1 else np.nan
            rsd = sd / mean_c * 100
            rec = mean_c / r["Ca"] * 100 if pd.notna(r["Ca"]) and r["Ca"] > 0 else np.nan
        ok = np.isfinite(rec) and rmin <= rec <= rmax and (np.isnan(rsd) or rsd < rsd_max)
        out.append({"No": i + 1, "Campuran": " + ".join(parts), "Abs rata-rata": np.mean(ab) if ab else np.nan,
                    "Conc Ca (mg/L)": mean_c, "SD": sd, "% RSD": rsd, "% Recovery": rec,
                    "Status": ("✅ Lulus" if ok else "❌ Tidak lulus") if np.isfinite(rec) else "-", "_ok": bool(ok)})
    res = pd.DataFrame(out)
    if len(res):
        st.markdown(f"**Hasil** (lulus bila recovery {rmin}–{rmax}% dan RSD < {rsd_max}%; RSD dihitung bila ulangan ≥ 2)")
        show = res.drop(columns="_ok")
        st.dataframe(show, hide_index=True, **W, column_config={
            "Abs rata-rata": st.column_config.NumberColumn(format="%.4f"),
            "Conc Ca (mg/L)": st.column_config.NumberColumn(format="%.4f"),
            "SD": st.column_config.NumberColumn(format="%.4f"),
            "% RSD": st.column_config.NumberColumn(format="%.2f"),
            "% Recovery": st.column_config.NumberColumn(format="%.1f")})
        rd = res.dropna(subset=["% Recovery"])
        if len(rd):
            rd = rd.assign(Label=rd["No"].astype(str) + ". " + rd["Campuran"])
            bars = alt.Chart(rd).mark_bar().encode(
                x=alt.X("Label:N", sort=None, title=None, axis=alt.Axis(labelAngle=-40, labelLimit=220)),
                y=alt.Y("% Recovery:Q", title="% Recovery"),
                color=alt.condition("datum._ok", alt.value("#16794a"), alt.value("#b42318")))
            rules = alt.Chart(pd.DataFrame({"y": [rmin, rmax]})).mark_rule(strokeDash=[5, 4]).encode(y="y:Q")
            st.altair_chart(bars + rules, **W)
        st.download_button("Unduh hasil (CSV)", show.to_csv(index=False).encode("utf-8"), "hasil_gangguan_ca.csv", "text/csv")
    if fitres:
        st.subheader("4. Estimasi batas deteksi dan kuantitasi")
        l1, l2, l3 = st.columns(3)
        l1.metric("Sy/x", f(syx, 4)); l2.metric("LOD (mg/L)", f(3.3 * syx / m, 3)); l3.metric("LOQ (mg/L)", f(10 * syx / m, 3))
        st.caption("LOD = 3,3·Sy/x / m dan LOQ = 10·Sy/x / m [9].")

# ---------------- simulasi 3D (memakai data dari tab Perhitungan) ----------------
def s(v):
    if isinstance(v, str):
        return v
    return "" if v is None or pd.isna(v) else f"{float(v):g}"

def sim_html():
    D = {"prep": [[str(r[0]), s(r[1]), s(r[2]), str(r[3]), s(r[4]), s(r[5]), s(r[6]), s(r[7])]
                  for r in prep.itertuples(index=False)],
         "stock": s(stock),
         "std": [[s(a), s(b_), s(c_), s(d_)] for a, b_, c_, d_ in std.itertuples(index=False)],
         "reps": int(n),
         "trt": [[s(v) for v in row] for row in trt.itertuples(index=False)]}
    html = (HERE / "simulator.html").read_text(encoding="utf-8")
    inject = ("<script>window.__DATA__=" + json.dumps(D, ensure_ascii=False) + ";</script>"
              "<style>nav,#t2,#t3,#t4{display:none!important}header{padding-bottom:12px}</style>")
    html = html.replace("<body>", "<body>" + inject, 1)
    html = html.replace("let D=clone(NB);", "let D=window.__DATA__?window.__DATA__:clone(NB);", 1)
    html = html.replace("if(sv&&sv.prep", "if(!window.__DATA__&&sv&&sv.prep", 1)
    return html

with tab_sim:
    st.caption("Seret untuk memutar, cubit atau scroll untuk zoom, klik komponen untuk info. "
               "Simulasi memakai data dari tab Perhitungan.")
    if hasattr(st, "iframe"):
        st.iframe(sim_html(), height=1500)
    else:
        components.html(sim_html(), height=1500, scrolling=True)

# ---------------- teori & referensi ----------------
with tab_theory:
    st.markdown("""
### Prinsip spektrofotometri serapan atom (SSA)
Atom bebas unsur dalam keadaan dasar menyerap radiasi pada panjang gelombang resonansinya. Lampu katoda berongga (HCL) Ca memancarkan
garis 422,7 nm. Larutan sampel dikabutkan, dicampur dengan udara dan asetilena, lalu dibawa ke nyala (sekitar 2300 °C) yang menguapkan
pelarut dan mengubah garam menjadi atom Ca. Detektor mengukur radiasi yang tersisa [1][2][3].

Hukum Lambert-Beer: **A = log(I₀/I) = ε b c**, sehingga absorbansi sebanding dengan konsentrasi dan kurva kalibrasi berbentuk garis lurus
**A = m·C + b** pada rentang linier [2][10].

### Gangguan pada penetapan Ca
- **Gangguan kimia oleh fosfat dan sulfat.** PO₄³⁻ dan SO₄²⁻ membentuk senyawa Ca yang stabil terhadap panas, sehingga tidak seluruhnya
  teratomisasi dalam nyala udara-asetilena. Absorbansi turun dan hasil lebih rendah dari sebenarnya. Pengaruh fosfat jauh lebih besar daripada sulfat [1][2][5].
- **La³⁺ sebagai releasing agent.** Lantanum berikatan lebih kuat dengan fosfat/sulfat daripada Ca sehingga Ca terbebas [1][5].
- **Sr²⁺ sebagai releasing agent alternatif.** Stronsium juga dipakai untuk membebaskan Ca, sehingga efeknya dapat dibandingkan dengan La [1].
- **EDTA sebagai protecting agent.** Kompleks Ca-EDTA stabil tetapi mudah terurai di nyala, sehingga Ca terlindung dari anion pengganggu [1][2].
- **Alternatif.** Nyala N₂O-asetilena (sekitar 2700 °C) menguraikan fosfat, tetapi menaikkan ionisasi Ca sehingga perlu penekan ionisasi (K atau Cs) [1][2].

### Kriteria keberterimaan
- % Recovery = konsentrasi terukur / konsentrasi nominal × 100 (default 85–115%).
- % RSD = SD / rata-rata × 100 (default < 5%).
- Koefisien korelasi (r) kurva kalibrasi idealnya ≥ 0,995 [9]. Sesuaikan dengan prosedur laboratorium Anda.
""")

with tab_ref:
    st.markdown("""
1. Welz, B., & Sperling, M. (1999). *Atomic Absorption Spectrometry* (3rd ed.). Wiley-VCH.
2. Skoog, D. A., Holler, F. J., & Crouch, S. R. (2018). *Principles of Instrumental Analysis* (7th ed.). Cengage Learning.
3. Walsh, A. (1955). The application of atomic absorption spectra to chemical analysis. *Spectrochimica Acta, 7*, 108–117.
4. Beaty, R. D., & Kerber, J. D. (1993). *Concepts, Instrumentation and Techniques in Atomic Absorption Spectrophotometry* (2nd ed.). Perkin-Elmer.
5. APHA, AWWA, & WEF. *Standard Methods for the Examination of Water and Wastewater*, Method 3111 (Metals by flame atomic absorption spectrometry).
6. BSN. SNI 6989.56:2009, Air dan air limbah – Bagian 56: Cara uji kalsium (Ca) dengan spektrofotometri serapan atom (SSA)-nyala.
7. GBC Scientific Equipment. *SensAA Dual Atomic Absorption Spectrometer: operation manual*.
8. AOAC International. *Official Methods of Analysis*, Method 968.08 (minerals in animal feed, atomic absorption method).
9. Magnusson, B., & Örnemark, U. (Eds.). (2014). *Eurachem Guide: The Fitness for Purpose of Analytical Methods* (2nd ed.).
10. Harris, D. C. (2016). *Quantitative Chemical Analysis* (9th ed.). W. H. Freeman.

*Periksa kembali edisi, nomor metode, dan halaman pada sumber asli sebelum dicantumkan dalam laporan. Nomor SNI dan metode AOAC khususnya perlu diverifikasi.*
""")
