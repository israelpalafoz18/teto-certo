"""
Teto Certo · Panorama do Investidor em Tempo Real
Dashboard Streamlit com dados de mercado via yfinance, AwesomeAPI e Banco Central (SGS).

Executar:
    pip install -r requirements.txt
    streamlit run app.py
"""

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# Configuração geral
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Teto Certo · Panorama do Investidor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ = ZoneInfo("America/Sao_Paulo")
CACHE_TTL = 60  # segundos de cache para cotações
HTTP_TIMEOUT = 10  # segundos por requisição HTTP

TICKER_IBOV = "^BVSP"
TICKER_IFIX = "IFIX.SA"
TICKERS_B3 = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBAS3.SA", "BBDC4.SA"]

AWESOME_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL"
BCB_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json"
SGS_SELIC_META = 432  # Meta Selic definida pelo Copom (% a.a.)
SGS_IPCA_MENSAL = 433  # IPCA variação mensal (%)

# Valores de referência usados apenas se a API do Banco Central falhar.
# Atualize-os manualmente quando necessário.
FALLBACK_SELIC = 15.00
FALLBACK_IPCA_12M = 5.17
FALLBACK_REF = "valor de referência estático"


PERFIS = {
    "Conservador": {
        "Renda Fixa Pós (CDI/Selic)": 50,
        "Tesouro IPCA+": 25,
        "Renda Fixa Prefixada": 10,
        "Fundos Imobiliários": 5,
        "Ações Brasil": 5,
        "Internacional": 5,
    },
    "Moderado": {
        "Renda Fixa Pós (CDI/Selic)": 30,
        "Tesouro IPCA+": 20,
        "Renda Fixa Prefixada": 5,
        "Fundos Imobiliários": 15,
        "Ações Brasil": 20,
        "Internacional": 10,
    },
    "Arrojado": {
        "Renda Fixa Pós (CDI/Selic)": 10,
        "Tesouro IPCA+": 10,
        "Renda Fixa Prefixada": 5,
        "Fundos Imobiliários": 15,
        "Ações Brasil": 40,
        "Internacional": 20,
    },
}

# Paleta (Dark Mode executivo)
COR_FUNDO = "#0B0E14"
COR_PAINEL = "#11151C"
COR_BORDA = "#1F2632"
COR_TEXTO = "#E8EAED"
COR_TEXTO_2 = "#9AA3AF"
COR_TEXTO_3 = "#6B7480"
COR_DESTAQUE = "#3987E5"
COR_ALTA = "#16C784"
COR_BAIXA = "#EA3943"

# Ordem fixa de cores categóricas (validada para daltonismo em fundo escuro)
CORES_ALOCACAO = ["#3987E5", "#D95926", "#199E70", "#C98500", "#D55181", "#9085E9"]

FONTE = "Inter, 'Segoe UI', Roboto, sans-serif"

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, .stApp, [class*="css"] {{ font-family: {FONTE}; }}
    .stApp {{ background-color: {COR_FUNDO}; color: {COR_TEXTO}; }}
    .block-container {{ padding: 1.6rem 2.2rem 2rem 2.2rem; max-width: 1480px; }}

    /* Oculta elementos de desenvolvimento do Streamlit */
    [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], footer,
    [data-testid="stDecoration"] {{ display: none !important; }}
    [data-testid="stHeader"] {{ background: transparent; }}

    /* Barra lateral */
    [data-testid="stSidebar"] {{ background-color: #080A0F; border-right: 1px solid {COR_BORDA}; }}
    [data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
    .marca {{ display: flex; align-items: center; gap: 10px; margin: 0 0 4px 0; }}
    .marca-logo {{ width: 34px; height: 34px; border-radius: 8px; background: {COR_DESTAQUE};
                   display: flex; align-items: center; justify-content: center;
                   color: #fff; font-weight: 700; font-size: 15px; letter-spacing: .02em; }}
    .marca-nome {{ font-size: 17px; font-weight: 700; color: {COR_TEXTO}; letter-spacing: .01em; line-height: 1.1; }}
    .marca-sub {{ font-size: 12px; color: {COR_TEXTO_2}; }}
    .rotulo-lateral {{ font-size: 11px; font-weight: 600; color: {COR_TEXTO_3};
                       text-transform: uppercase; letter-spacing: .08em; margin: 22px 0 8px 0; }}

    /* Cabeçalho */
    .topo {{ display: flex; justify-content: space-between; align-items: flex-end;
             border-bottom: 1px solid {COR_BORDA}; padding-bottom: 14px; margin-bottom: 18px; flex-wrap: wrap; gap: 8px; }}
    .topo h1 {{ font-size: 26px; font-weight: 700; margin: 0; padding: 0; color: {COR_TEXTO}; letter-spacing: -.01em; }}
    .topo .sub {{ font-size: 13px; color: {COR_TEXTO_2}; margin-top: 2px; }}
    .topo .hora {{ font-size: 12px; color: {COR_TEXTO_2}; text-align: right; }}
    .topo .hora b {{ color: {COR_TEXTO}; font-weight: 600; }}

    /* Cards de indicadores */
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .kpi {{ background: {COR_PAINEL}; border: 1px solid {COR_BORDA}; border-radius: 10px;
            padding: 14px 16px 12px 16px; display: flex; flex-direction: column; gap: 6px; min-height: 118px; }}
    .kpi-rotulo {{ font-size: 11px; font-weight: 600; color: {COR_TEXTO_2}; text-transform: uppercase; letter-spacing: .08em; }}
    .kpi-valor {{ font-size: 24px; font-weight: 700; color: {COR_TEXTO}; font-variant-numeric: tabular-nums;
                  white-space: nowrap; letter-spacing: -.01em; }}
    .kpi-valor .un {{ font-size: 13px; font-weight: 500; color: {COR_TEXTO_2}; margin-left: 4px; }}
    .kpi-delta {{ font-size: 12.5px; font-weight: 600; font-variant-numeric: tabular-nums; }}
    .kpi-delta.alta {{ color: {COR_ALTA}; }}
    .kpi-delta.baixa {{ color: {COR_BAIXA}; }}
    .kpi-delta.neutra {{ color: {COR_TEXTO_2}; font-weight: 500; }}
    .kpi-rodape {{ font-size: 11px; color: {COR_TEXTO_3}; margin-top: auto; }}
    .kpi.indisponivel .kpi-valor {{ color: {COR_TEXTO_3}; font-size: 18px; }}

    /* Painéis */
    [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .painel-cab) {{
        background: {COR_PAINEL}; border: 1px solid {COR_BORDA} !important; border-radius: 10px;
    }}
    .painel-cab {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 2px; }}
    .painel-titulo {{ font-size: 15px; font-weight: 600; color: {COR_TEXTO}; }}
    .painel-sub {{ font-size: 12px; color: {COR_TEXTO_2}; }}

    /* Botão primário */
    .stButton > button[kind="primary"] {{ background: {COR_DESTAQUE}; border: 0; border-radius: 8px;
                                          font-weight: 600; height: 42px; }}
    .stButton > button[kind="primary"]:hover {{ background: #4A95EC; }}

    .nota {{ font-size: 11.5px; color: {COR_TEXTO_3}; margin-top: 6px; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Utilitários de formatação (padrão brasileiro)
# ---------------------------------------------------------------------------
def fmt_num(valor, casas=2):
    """Formata número no padrão pt-BR (1.234,56)."""
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_sinal(valor, casas=2):
    """Número com sinal explícito (+/-), usado nos deltas dos cards."""
    if valor is None or pd.isna(valor):
        return "—"
    return ("+" if valor > 0 else "") + fmt_num(valor, casas)


def fmt_brl(valor, casas=2):
    return "—" if valor is None or pd.isna(valor) else f"R$ {fmt_num(valor, casas)}"


def fmt_pct(valor, casas=2, sinal=True):
    if valor is None or pd.isna(valor):
        return "—"
    prefixo = "+" if sinal and valor > 0 else ""
    return f"{prefixo}{fmt_num(valor, casas)}%"


def fmt_volume(valor):
    """Volume financeiro abreviado (mi / bi)."""
    if valor is None or pd.isna(valor):
        return "—"
    if abs(valor) >= 1e9:
        return f"R$ {fmt_num(valor / 1e9, 2)} bi"
    if abs(valor) >= 1e6:
        return f"R$ {fmt_num(valor / 1e6, 2)} mi"
    return fmt_brl(valor)


def para_float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Coleta de dados (cada função trata seus próprios erros)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def buscar_indice(ticker):
    """Retorna dict com último valor, variação em pontos e variação % de um índice."""
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            return {"ok": False, "erro": f"Sem dados retornados para {ticker}."}
        ultimo = float(hist["Close"].iloc[-1])
        anterior = float(hist["Close"].iloc[-2]) if len(hist) > 1 else None
        variacao = ultimo - anterior if anterior else None
        variacao_pct = (variacao / anterior * 100) if anterior else None
        data_ref = hist.index[-1].to_pydatetime()
        return {
            "ok": True,
            "valor": ultimo,
            "variacao": variacao,
            "variacao_pct": variacao_pct,
            "data": data_ref,
        }
    except Exception as exc:  # noqa: BLE001 - qualquer falha de rede/parse deve ser tolerada
        return {"ok": False, "erro": f"Falha ao consultar {ticker}: {exc}"}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def buscar_moedas():
    """Cotações USD/BRL e EUR/BRL via AwesomeAPI."""
    try:
        resp = requests.get(AWESOME_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()
        resultado = {}
        for chave, nome in (("USDBRL", "Dólar Comercial"), ("EURBRL", "Euro")):
            item = dados.get(chave)
            if not item:
                resultado[chave] = {"ok": False, "erro": f"{nome} ausente na resposta."}
                continue
            resultado[chave] = {
                "ok": True,
                "nome": nome,
                "compra": para_float(item.get("bid")),
                "venda": para_float(item.get("ask")),
                "variacao": para_float(item.get("varBid")),
                "variacao_pct": para_float(item.get("pctChange")),
                "atualizado": item.get("create_date", ""),
            }
        return {"ok": True, "dados": resultado}
    except requests.exceptions.Timeout:
        return {"ok": False, "erro": "Tempo esgotado ao consultar a AwesomeAPI."}
    except requests.exceptions.HTTPError as exc:
        codigo = exc.response.status_code if exc.response is not None else "?"
        msg = "limite de requisições atingido" if codigo == 429 else f"HTTP {codigo}"
        return {"ok": False, "erro": f"AwesomeAPI indisponível ({msg})."}
    except (requests.exceptions.RequestException, ValueError) as exc:
        return {"ok": False, "erro": f"Erro ao consultar a AwesomeAPI: {exc}"}


def _consultar_sgs(serie, n):
    resp = requests.get(BCB_SGS_URL.format(serie=serie, n=n), timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    dados = resp.json()
    if not isinstance(dados, list) or not dados:
        raise ValueError(f"Resposta vazia para a série SGS {serie}.")
    return dados


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_selic():
    """Meta Selic (SGS 432). Usa valor estático se a API falhar."""
    try:
        dados = _consultar_sgs(SGS_SELIC_META, 1)
        valor = float(str(dados[-1]["valor"]).replace(",", "."))
        return {"ok": True, "valor": valor, "data": dados[-1]["data"], "fonte": "Banco Central (SGS 432)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "valor": FALLBACK_SELIC, "data": None, "fonte": FALLBACK_REF, "erro": str(exc)}


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_ipca_12m():
    """IPCA acumulado em 12 meses, composto a partir da série mensal (SGS 433)."""
    try:
        dados = _consultar_sgs(SGS_IPCA_MENSAL, 12)
        if len(dados) < 12:
            raise ValueError("Menos de 12 meses retornados pela série SGS 433.")
        fator = 1.0
        for item in dados:
            fator *= 1 + float(str(item["valor"]).replace(",", ".")) / 100
        acumulado = (fator - 1) * 100
        return {"ok": True, "valor": acumulado, "data": dados[-1]["data"], "fonte": "Banco Central (SGS 433)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "valor": FALLBACK_IPCA_12M, "data": None, "fonte": FALLBACK_REF, "erro": str(exc)}


@st.cache_data(ttl=CACHE_TTL * 5, show_spinner=False)
def buscar_historico_ibov():
    """Fechamentos diários do Ibovespa nos últimos 12 meses."""
    try:
        hist = yf.Ticker(TICKER_IBOV).history(period="1y", interval="1d", auto_adjust=False)
        hist = hist.dropna(subset=["Close"])
        if hist.empty:
            return {"ok": False, "erro": "Histórico do Ibovespa veio vazio."}
        serie = hist["Close"].copy()
        serie.index = serie.index.tz_localize(None) if serie.index.tz is not None else serie.index
        return {"ok": True, "serie": serie}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "erro": f"Falha ao obter histórico do Ibovespa: {exc}"}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def buscar_radar(tickers):
    """Tabela de ativos da B3: último preço, máxima, mínima, volume financeiro e variação."""
    linhas, erros = [], []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            hist = hist.dropna(subset=["Close"])
            if hist.empty:
                erros.append(f"{ticker}: sem dados")
                continue
            dia = hist.iloc[-1]
            anterior = float(hist["Close"].iloc[-2]) if len(hist) > 1 else None
            ultimo = float(dia["Close"])
            linhas.append(
                {
                    "Ticker": ticker.replace(".SA", ""),
                    "Último Preço": ultimo,
                    "Variação %": ((ultimo / anterior - 1) * 100) if anterior else None,
                    "Máxima do Dia": float(dia["High"]),
                    "Mínima do Dia": float(dia["Low"]),
                    # Volume financeiro aproximado: quantidade negociada x preço de fechamento
                    "Volume Financeiro": float(dia["Volume"]) * ultimo,
                }
            )
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{ticker}: {exc}")
    return {"df": pd.DataFrame(linhas), "erros": erros}




# ---------------------------------------------------------------------------
# Componentes visuais
# ---------------------------------------------------------------------------
def classe_delta(valor):
    if valor is None or pd.isna(valor):
        return "neutra"
    return "alta" if valor >= 0 else "baixa"


def seta(valor):
    if valor is None or pd.isna(valor):
        return ""
    return "▲" if valor >= 0 else "▼"


def html_kpi(rotulo, valor, unidade="", delta=None, delta_ref=None, rodape="", dica="", indisponivel=False):
    """Monta o HTML de um card de indicador."""
    classe = "kpi indisponivel" if indisponivel else "kpi"
    un = f"<span class='un'>{escape(unidade)}</span>" if unidade else ""
    if delta:
        cls = classe_delta(delta_ref)
        linha_delta = f"<div class='kpi-delta {cls}'>{seta(delta_ref)} {escape(delta)}</div>"
    else:
        linha_delta = "<div class='kpi-delta neutra'>&nbsp;</div>"
    return (
        f"<div class='{classe}' title='{escape(dica, quote=True)}'>"
        f"<div class='kpi-rotulo'>{escape(rotulo)}</div>"
        f"<div class='kpi-valor'>{escape(valor)}{un}</div>"
        f"{linha_delta}"
        f"<div class='kpi-rodape'>{escape(rodape)}</div>"
        "</div>"
    )


def kpi_indisponivel(rotulo, erro, fonte):
    return html_kpi(rotulo, "Indisponível", rodape=fonte, dica=erro, indisponivel=True)


def cabecalho_painel(titulo, subtitulo=""):
    st.markdown(
        f"<div class='painel-cab'><span class='painel-titulo'>{escape(titulo)}</span>"
        f"<span class='painel-sub'>{escape(subtitulo)}</span></div>",
        unsafe_allow_html=True,
    )


def layout_base(fig, altura):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONTE, color=COR_TEXTO_2, size=12),
        margin=dict(t=8, b=8, l=8, r=8),
        height=altura,
        separators=",.",
        hoverlabel=dict(bgcolor="#1A2030", bordercolor=COR_BORDA, font=dict(family=FONTE, color=COR_TEXTO, size=12)),
    )
    return fig


def grafico_alocacao(perfil):
    pesos = PERFIS[perfil]
    fig = go.Figure(
        go.Pie(
            labels=list(pesos.keys()),
            values=list(pesos.values()),
            hole=0.68,
            sort=False,
            direction="clockwise",
            marker=dict(colors=CORES_ALOCACAO, line=dict(color=COR_PAINEL, width=2)),
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>%{value}% da carteira<extra></extra>",
        )
    )
    layout_base(fig, 300)
    fig.update_layout(
        showlegend=False,
        annotations=[
            dict(text="PERFIL", x=0.5, y=0.57, showarrow=False, font=dict(size=11, color=COR_TEXTO_3)),
            dict(text=f"<b>{perfil}</b>", x=0.5, y=0.45, showarrow=False, font=dict(size=18, color=COR_TEXTO)),
        ],
    )
    return fig


def legenda_alocacao(perfil):
    linhas = []
    for (classe, peso), cor in zip(PERFIS[perfil].items(), CORES_ALOCACAO):
        linhas.append(
            "<div style='display:flex;align-items:center;justify-content:space-between;"
            f"padding:7px 0;border-bottom:1px solid {COR_BORDA};font-size:13px'>"
            f"<span style='display:flex;align-items:center;gap:9px;color:{COR_TEXTO}'>"
            f"<span style='width:10px;height:10px;border-radius:3px;background:{cor};display:inline-block'></span>"
            f"{escape(classe)}</span>"
            f"<span style='color:{COR_TEXTO};font-weight:600;font-variant-numeric:tabular-nums'>{peso}%</span></div>"
        )
    return "<div style='margin-top:18px'>" + "".join(linhas) + "</div>"


MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def ticks_mensais(indice, passo=2):
    """Marcações do eixo X no primeiro pregão de cada mês, com rótulos em português."""
    vistos, primeiros = set(), []
    for data in indice:
        if (data.year, data.month) not in vistos:
            vistos.add((data.year, data.month))
            primeiros.append(data)
    valores = primeiros[1::passo]
    textos = [f"{MESES_PT[d.month - 1]}/{d.strftime('%y')}" for d in valores]
    return valores, textos


def grafico_historico(serie):
    fig = go.Figure(
        go.Scatter(
            x=serie.index,
            y=serie.values,
            mode="lines",
            line=dict(color=COR_DESTAQUE, width=2),
            fill="tozeroy",
            fillcolor="rgba(57,135,229,0.10)",
            hovertemplate="%{x|%d/%m/%Y}  <b>%{y:,.0f} pts</b><extra></extra>",
            name="Ibovespa",
        )
    )
    minimo, maximo = float(serie.min()), float(serie.max())
    folga = (maximo - minimo) * 0.08
    marcas, rotulos = ticks_mensais(serie.index)
    layout_base(fig, 330)
    fig.update_layout(
        hovermode="x",
        showlegend=False,
        xaxis=dict(
            showgrid=False, showline=True, linecolor=COR_BORDA, color=COR_TEXTO_2,
            tickvals=marcas, ticktext=rotulos,
            showspikes=True, spikemode="across", spikecolor=COR_TEXTO_3, spikethickness=1, spikedash="dot",
        ),
        yaxis=dict(
            gridcolor=COR_BORDA, zeroline=False, color=COR_TEXTO_2, side="right",
            tickformat=",.0f", range=[minimo - folga, maximo + folga],
        ),
    )
    return fig


def cor_variacao(valor):
    if valor is None or pd.isna(valor):
        return f"color: {COR_TEXTO_2}"
    return f"color: {COR_ALTA if valor >= 0 else COR_BAIXA}; font-weight: 600"


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<div class='marca'><div class='marca-logo'>TC</div>"
        "<div><div class='marca-nome'>Teto Certo</div>"
        "<div class='marca-sub'>Panorama do Investidor</div></div></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='rotulo-lateral'>Dados</div>", unsafe_allow_html=True)
    if st.button("Atualizar Dados", icon=":material/refresh:", width="stretch", type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("<div class='rotulo-lateral'>Perfil de Investidor</div>", unsafe_allow_html=True)
    perfil = st.radio(
        "Perfil de Investidor", list(PERFIS.keys()), index=1, label_visibility="collapsed"
    )

# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------
with st.spinner("Consultando mercados..."):
    ibov = buscar_indice(TICKER_IBOV)
    ifix = buscar_indice(TICKER_IFIX)
    moedas = buscar_moedas()
    selic = buscar_selic()
    ipca = buscar_ipca_12m()

# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
agora = datetime.now(TZ)
pregao = f"Pregão de referência: <b>{ibov['data'].strftime('%d/%m/%Y')}</b> · " if ibov["ok"] else ""
st.markdown(
    "<div class='topo'><div><h1>Panorama do Investidor em Tempo Real</h1>"
    "<div class='sub'>Índices, câmbio, juros e ações da B3 em uma única tela</div></div>"
    f"<div class='hora'>{pregao}Atualizado às <b>{agora.strftime('%H:%M:%S')}</b> de {agora.strftime('%d/%m/%Y')} (Brasília)</div></div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 1. Cards de topo
# ---------------------------------------------------------------------------
cards = []

if ibov["ok"]:
    delta = None
    if ibov["variacao"] is not None:
        delta = f"{fmt_sinal(ibov['variacao'], 0)} pts · {fmt_pct(ibov['variacao_pct'])}"
    cards.append(html_kpi("Ibovespa", fmt_num(ibov["valor"], 0), "pts", delta, ibov["variacao"], "B3 · Yahoo Finance"))
else:
    cards.append(kpi_indisponivel("Ibovespa", ibov["erro"], "B3 · Yahoo Finance"))

if ifix["ok"]:
    delta = fmt_pct(ifix["variacao_pct"]) if ifix["variacao_pct"] is not None else None
    cards.append(html_kpi("IFIX", fmt_num(ifix["valor"], 0), "pts", delta, ifix["variacao_pct"], "B3 · Yahoo Finance"))
else:
    cards.append(kpi_indisponivel("IFIX", ifix["erro"], "B3 · Yahoo Finance"))

for chave, titulo in (("USDBRL", "Dólar Comercial"), ("EURBRL", "Euro")):
    if not moedas["ok"]:
        cards.append(kpi_indisponivel(titulo, moedas["erro"], "AwesomeAPI"))
        continue
    moeda = moedas["dados"].get(chave, {"ok": False, "erro": "Sem dados."})
    if moeda["ok"] and moeda["compra"] is not None:
        delta = None
        if moeda["variacao"] is not None:
            delta = f"{fmt_sinal(moeda['variacao'], 4)} · {fmt_pct(moeda['variacao_pct'])}"
        cards.append(
            html_kpi(titulo, fmt_brl(moeda["compra"], 4), "", delta, moeda["variacao"],
                     "Compra · AwesomeAPI", dica=f"Atualizado em {moeda['atualizado']}")
        )
    else:
        cards.append(kpi_indisponivel(titulo, moeda.get("erro", "Sem dados."), "AwesomeAPI"))

if selic["ok"]:
    rodape_selic = f"Copom · vigente desde {selic['data']}"
    dica_selic = selic["fonte"]
else:
    rodape_selic = "Referência estática"
    dica_selic = f"API do Banco Central indisponível: {selic['erro']}"
cards.append(html_kpi("Selic Meta", fmt_num(selic["valor"], 2), "% a.a.", rodape=rodape_selic, dica=dica_selic))

if ipca["ok"]:
    rodape_ipca = f"IBGE · até {ipca['data'][3:]}"
    dica_ipca = ipca["fonte"]
else:
    rodape_ipca = "Referência estática"
    dica_ipca = f"API do Banco Central indisponível: {ipca['erro']}"
cards.append(html_kpi("IPCA 12 meses", fmt_num(ipca["valor"], 2), "%", rodape=rodape_ipca, dica=dica_ipca))

st.markdown("<div class='kpis'>" + "".join(cards) + "</div>", unsafe_allow_html=True)

falhas = [d["erro"] for d in (ibov, ifix) if not d["ok"]]
if not moedas["ok"]:
    falhas.append(moedas["erro"])
if falhas:
    with st.expander("Algumas fontes não responderam", icon=":material/warning:", expanded=False):
        for falha in falhas:
            st.caption(falha)

# ---------------------------------------------------------------------------
# 2. Alocação dinâmica + 3. Histórico
# ---------------------------------------------------------------------------
col_aloc, col_hist = st.columns([1, 1.7], gap="medium")

with col_aloc:
    with st.container(border=True):
        cabecalho_painel("Alocação Sugerida", f"Perfil {perfil}")
        g1, g2 = st.columns([1, 1.05])
        with g1:
            st.plotly_chart(grafico_alocacao(perfil), width="stretch", config={"displayModeBar": False})
        with g2:
            st.markdown(legenda_alocacao(perfil), unsafe_allow_html=True)

with col_hist:
    with st.container(border=True):
        historico = buscar_historico_ibov()
        if historico["ok"]:
            serie = historico["serie"]
            periodo = f"{serie.index[0].strftime('%d/%m/%Y')} a {serie.index[-1].strftime('%d/%m/%Y')}"
            cabecalho_painel("Ibovespa · Últimos 12 Meses", periodo)
            st.plotly_chart(grafico_historico(serie), width="stretch", config={"displayModeBar": False})
        else:
            cabecalho_painel("Ibovespa · Últimos 12 Meses")
            st.error(historico["erro"])

# ---------------------------------------------------------------------------
# 4. Radar de ações
# ---------------------------------------------------------------------------
radar = buscar_radar(tuple(TICKERS_B3))
df = radar["df"]

with st.container(border=True):
    cabecalho_painel("Radar de Ações B3", "Pregão mais recente · Yahoo Finance")
    if df.empty:
        st.error("Não foi possível obter cotações dos ativos da B3 no momento.")
    else:
        tabela = (
            df.style.format(
                {
                    "Último Preço": fmt_brl,
                    "Variação %": lambda v: f"{seta(v)} {fmt_pct(v)}",
                    "Máxima do Dia": fmt_brl,
                    "Mínima do Dia": fmt_brl,
                    "Volume Financeiro": fmt_volume,
                }
            )
            .map(cor_variacao, subset=["Variação %"])
            .set_properties(subset=["Ticker"], **{"font-weight": "700"})
        )
        st.dataframe(tabela, width="stretch", hide_index=True, height=36 * (len(df) + 1) + 3)
        st.markdown(
            "<div class='nota'>Volume financeiro estimado: quantidade negociada × preço de fechamento. "
            "Cotações da B3 via Yahoo Finance podem ter atraso de até 15 minutos.</div>",
            unsafe_allow_html=True,
        )

    if radar["erros"]:
        with st.expander("Ativos sem cotação", icon=":material/warning:", expanded=False):
            for erro in radar["erros"]:
                st.caption(erro)
