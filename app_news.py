import html
import re
from datetime import datetime
import feedparser
import requests
import streamlit as st

# =====================================================================
# CONFIGURAÇÃO GERAL
# =====================================================================
st.set_page_config(
    page_title="Radar de Inteligência Diária · Hub",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "favoritos" not in st.session_state:
    st.session_state.favoritos = []

# =====================================================================
# CATÁLOGO DE FEEDS CORRIGIDO (FEEDS ATIVOS EM TEMPO REAL)
# =====================================================================
FEEDS = {
    "🏎️ Carros & Motores": [
        {"nome": "Motor1 Brasil", "url": "https://motor1.uol.com.br/rss/news/all/", "tag": "LANÇAMENTOS"},
        {"nome": "Quatro Rodas", "url": "https://quatrorodas.abril.com.br/feed/", "tag": "TESTES"},
        {"nome": "Autoesporte", "url": "https://autoesporte.globo.com/rss/autoesporte/", "tag": "MERCADO AUTO"},
    ],
    "💻 Tecnologia": [
        {"nome": "Tecnoblog", "url": "https://tecnoblog.net/feed/", "tag": "TECH BR"},
        {"nome": "Canaltech", "url": "https://canaltech.com.br/rss/", "tag": "HARDWARE & IA"},
        {"nome": "Olhar Digital", "url": "https://olhardigital.com.br/feed/", "tag": "INOVAÇÃO"},
    ],
    "🏁 Fórmula 1": [
        {"nome": "Motorsport.com BR", "url": "https://motorsport.uol.com.br/rss/f1/news/", "tag": "F1 TELEMETRIA"},
        {"nome": "Grande Prêmio", "url": "https://www.grandepremio.com.br/feed/", "tag": "PADDOCK"},
    ],
    "📍 Cotidiano Local (SP)": [
        # Feeds ativos e em tempo real de São Paulo (Folha, R7 e Metrópoles)
        {"nome": "Folha SP / Cotidiano", "url": "https://feeds.folha.uol.com.br/cotidiano/rss091.xml", "tag": "CIDADE & TRÂNSITO"},
        {"nome": "Folha de S.Paulo", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml", "tag": "EM CIMA DA HORA"},
        {"nome": "R7 Notícias SP", "url": "https://noticias.r7.com/sao-paulo/feed.xml", "tag": "SP REGIONAL"},
    ],
    "🌐 Cotidiano Global": [
        {"nome": "BBC News Brasil", "url": "https://feeds.bbci.co.uk/portuguese/rss.xml", "tag": "BBC GLOBAL"},
        {"nome": "DW Brasil", "url": "https://rss.dw.com/rdf/rss-br-all", "tag": "GEOPOLÍTICA"},
        {"nome": "G1 Mundo", "url": "https://g1.globo.com/rss/g1/mundo/", "tag": "INTERNACIONAL"},
    ],
    "🏋️ Exercícios & Performance": [
        {"nome": "Eu Atleta (G1)", "url": "https://ge.globo.com/eu-atleta/rss.xml", "tag": "TREINO & CORRIDA"},
        {"nome": "G1 Saúde & Bem-Estar", "url": "https://g1.globo.com/rss/g1/saude/", "tag": "LONGEVIDADE"},
    ],
    "🏛️ Política & Poder": [
        {"nome": "Folha Política", "url": "https://feeds.folha.uol.com.br/poder/rss091.xml", "tag": "PODER & BASTIDORES"},
        {"nome": "Poder360", "url": "https://www.poder360.com.br/feed/", "tag": "BASTIDORES"},
        {"nome": "Agência Brasil - Política", "url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml", "tag": "BRASÍLIA"},
    ],
}

FALLBACK_IMG = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=800&auto=format&fit=crop"

# =====================================================================
# SERVIÇO METEOROLÓGICO LOCAL (SÃO PAULO)
# =====================================================================
@st.cache_data(ttl=900)
def fetch_sp_weather():
    """Obtém temperatura e condição de São Paulo em tempo real."""
    url = "https://api.open-meteo.com/v1/forecast?latitude=-23.5505&longitude=-46.6333&current=temperature_2m,relative_humidity_2m,weather_code&timezone=auto"
    try:
        res = requests.get(url, timeout=4).json()
        cur = res.get("current", {})
        code = cur.get("weather_code", 0)
        icones = {
            0: "☀️ Céu Limpo", 1: "🌤️ Pred. Limpo", 2: "⛅ Parc. Nublado", 3: "☁️ Nublado",
            45: "🌫️ Nevoeiro", 51: "🌦️ Garoa", 61: "🌧️ Chuva", 95: "⛈️ Tempestade"
        }
        condicao = icones.get(code, "🌤️ Estável")
        return {
            "temp": round(cur.get("temperature_2m", 0), 1),
            "umidade": cur.get("relative_humidity_2m", "--"),
            "condicao": condicao,
        }
    except Exception:
        return {"temp": "--", "umidade": "--", "condicao": "🌤️ Dados WX"}


# =====================================================================
# EXTRAÇÃO DE IMAGEM & TRATAMENTO DE TEXTO
# =====================================================================
def extract_image_url(entry):
    if "media_content" in entry and len(entry.media_content) > 0:
        url = entry.media_content[0].get("url")
        if url:
            return url

    if "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
        url = entry.media_thumbnail[0].get("url")
        if url:
            return url

    if "enclosures" in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("href")

    raw_html = entry.get("summary", "")
    if "content" in entry and len(entry.content) > 0:
        raw_html += " " + entry.content[0].get("value", "")

    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_html)
    if img_match:
        return img_match.group(1)

    return FALLBACK_IMG


def generate_tldr(texto: str, titulo: str) -> list:
    limpo = re.sub(r"\s+", " ", texto).strip()
    frases = [f.strip() for f in re.split(r"[.!?]", limpo) if len(f.strip()) > 18]
    
    pontos = []
    pontos.append(f"**Contexto Principal:** {titulo}")
    
    if len(frases) >= 1:
        pontos.append(f"**Destaque:** {frases[0]}.")
    if len(frases) >= 2:
        pontos.append(f"**Detalhe Adicional:** {frases[1]}.")
    else:
        pontos.append("**Ação:** Aceda à reportagem completa na fonte oficial para conferir a cobertura na íntegra.")
        
    return pontos[:3]


@st.cache_data(ttl=600)
def fetch_feed_articles(feed_list):
    artigos = []
    for item in feed_list:
        try:
            parsed = feedparser.parse(item["url"])
            for entry in parsed.entries[:9]:
                data_publicacao = "Hoje"
                timestamp = 0
                
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    timestamp = datetime(*entry.published_parsed[:6]).timestamp()
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    timestamp = datetime(*entry.updated_parsed[:6]).timestamp()

                if hasattr(entry, "published"):
                    data_publicacao = entry.published[:16]
                elif hasattr(entry, "updated"):
                    data_publicacao = entry.updated[:16]

                imagem = extract_image_url(entry)

                resumo = entry.get("summary", "")
                if "<" in resumo:
                    resumo = re.sub(r"<[^>]+>", "", resumo)
                resumo = html.unescape(resumo).strip()
                resumo_curto = (resumo[:115] + "...") if len(resumo) > 115 else resumo

                artigos.append({
                    "id": entry.link,
                    "titulo": html.unescape(entry.title),
                    "link": entry.link,
                    "fonte": item["nome"],
                    "tag": item["tag"],
                    "imagem": imagem,
                    "data": data_publicacao,
                    "timestamp": timestamp,
                    "resumo": resumo_curto,
                    "resumo_completo": resumo if resumo else entry.title,
                })
        except Exception:
            continue

    # Ordena para garantir as notícias mais recentes primeiro
    artigos.sort(key=lambda x: x["timestamp"], reverse=True)
    return artigos


# =====================================================================
# CSS CUSTOMIZADO
# =====================================================================
def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #07070F; color: #FFFFFF; }
    .stApp, [data-testid="stAppViewContainer"] { background: #07070F; }
    [data-testid="stHeader"] { background: transparent; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 0.8rem !important; max-width: 100% !important; padding-left: 2rem !important; padding-right: 2rem !important; }

    .hero-wrap { 
        background: linear-gradient(135deg, #0D0010 0%, #07070F 55%, #001015 100%); 
        border-bottom: 2px solid #00D2BE; 
        padding: 1.5rem 2rem 1.2rem; 
        margin-bottom: 1rem; 
        position: relative; 
        overflow: hidden; 
        border-radius: 0 0 12px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .hero-title { 
        font-family: 'Rajdhani', sans-serif !important; 
        font-size: 2.6rem !important; 
        font-weight: 700 !important; 
        color: #FFFFFF !important; 
        line-height: 1 !important; 
        margin: 0 !important; 
    }
    .hero-title .accent { 
        color: #00D2BE !important; 
        text-shadow: 0 0 18px rgba(0, 210, 190, 0.5); 
    }
    .hero-sub { 
        font-size: 0.72rem; 
        font-weight: 600; 
        letter-spacing: 0.25em; 
        text-transform: uppercase; 
        color: #CBD5E1; 
        margin: 0 0 0.3rem 0; 
    }

    .wx-widget {
        background: #0F0F1C;
        border: 1px solid #1C1C2E;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        display: flex;
        align-items: center;
        gap: 15px;
    }
    .wx-val {
        font-family: 'Rajdhani', sans-serif;
        font-size: 1.4rem;
        font-weight: 700;
        color: #00D2BE;
        line-height: 1;
    }

    .breaking-ticker {
        background: #0A0A16;
        border-left: 4px solid #FF8000;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        margin-bottom: 1.2rem;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .breaking-badge {
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.75rem;
        font-weight: 700;
        color: #FF8000;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .breaking-text {
        font-size: 0.85rem;
        color: #E2E8F0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        text-decoration: none;
    }
    .breaking-text:hover { color: #00D2BE; }

    .news-card {
        background: #0F0F1C;
        border: 1px solid #1C1C2E;
        border-radius: 10px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        transition: transform 0.2s, border-color 0.2s;
        overflow: hidden;
        margin-bottom: 1rem;
    }
    .news-card:hover {
        border-color: #00D2BE;
        transform: translateY(-3px);
    }
    .news-img-box {
        width: 100%;
        height: 160px;
        background-color: #07070F;
        overflow: hidden;
        position: relative;
    }
    .news-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .news-img-badge {
        position: absolute;
        top: 8px;
        left: 8px;
        background: rgba(7, 7, 15, 0.85);
        border: 1px solid rgba(0, 210, 190, 0.4);
        padding: 2px 7px;
        border-radius: 4px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.68rem;
        font-weight: 700;
        color: #00D2BE;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    .news-body {
        padding: 1.1rem;
    }
    .news-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.4rem;
    }
    .news-source { font-size: 0.72rem; color: #CBD5E1; font-weight: 600; }
    .news-title {
        font-family: 'Rajdhani', sans-serif;
        font-size: 1.18rem;
        font-weight: 700;
        line-height: 1.25;
        color: #FFFFFF;
        margin-bottom: 0.5rem;
        text-decoration: none;
        display: block;
    }
    .news-title:hover { color: #00D2BE; }
    .news-desc { font-size: 0.82rem; color: #A0AEC0; line-height: 1.35; margin-bottom: 0.8rem; }
    
    .news-action {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.85rem;
        font-weight: 700;
        color: #00D2BE;
        text-decoration: none;
        text-transform: uppercase;
    }

    button[data-baseweb="tab"] {
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: #CBD5E1 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #00D2BE !important;
        border-bottom-color: #00D2BE !important;
    }
    div[data-baseweb="input"] > div {
        background-color: #0F0F1C !important;
        border-color: #1C1C2E !important;
        color: #FFFFFF !important;
    }
    </style>
    """, unsafe_allow_html=True)


# =====================================================================
# RENDERIZADOR DE CARTÕES
# =====================================================================
def render_article_card(art: dict, key_prefix: str):
    card_html = f"""<div class="news-card">
<div class="news-img-box">
<img src="{art['imagem']}" class="news-img" loading="lazy" onerror="this.src='{FALLBACK_IMG}';">
<span class="news-img-badge">{art['tag']}</span>
</div>
<div class="news-body">
<div class="news-meta">
<span class="news-source">{art['fonte']}</span>
<span style="font-size:0.75rem; color:#718096;">{art['data']}</span>
</div>
<a href="{art['link']}" target="_blank" class="news-title">{art['titulo']}</a>
<p class="news-desc">{art['resumo']}</p>
<div style="border-top: 1px solid #1C1C2E; padding-top: 0.6rem; display: flex; justify-content: space-between; align-items: center;">
<a href="{art['link']}" target="_blank" class="news-action">Ler Artigo →</a>
</div>
</div>
</div>"""
    st.markdown(card_html, unsafe_allow_html=True)

    col_btn1, col_btn2 = st.columns([1, 1])
    links_guardados = [a["link"] for a in st.session_state.favoritos]
    is_saved = art["link"] in links_guardados

    with col_btn1:
        rotulo_btn = "⭐ Guardado" if is_saved else "☆ Guardar"
        if st.button(rotulo_btn, key=f"fav_{key_prefix}_{art['link']}", use_container_width=True):
            if is_saved:
                st.session_state.favoritos = [a for a in st.session_state.favoritos if a["link"] != art["link"]]
            else:
                st.session_state.favoritos.append(art)
            st.rerun()

    with col_btn2:
        with st.popover("⚡ TL;DR"):
            st.markdown("#### Resumo Estruturado")
            pontos = generate_tldr(art["resumo_completo"], art["titulo"])
            for p in pontos:
                st.markdown(f"• {p}")
            st.link_button("Aceder à Fonte Oficial", art["link"], use_container_width=True)


# =====================================================================
# APLICAÇÃO PRINCIPAL
# =====================================================================
def main():
    inject_custom_css()
    wx = fetch_sp_weather()

    st.markdown(f"""
    <div class="hero-wrap">
        <div>
            <p class="hero-sub">Centro de Controlo & Inteligência Diária</p>
            <h1 class="hero-title">Radar <span class="accent">Regional</span> & Mundo</h1>
        </div>
        <div class="wx-widget">
            <div>
                <span style="font-size:0.65rem; color:#A0AEC0; text-transform:uppercase; font-weight:700; letter-spacing:0.1em; display:block;">São Paulo · WX</span>
                <span class="wx-val">{wx['temp']}°C</span>
            </div>
            <div style="text-align:right;">
                <span style="font-size:0.8rem; color:#00E676; font-weight:600; display:block;">{wx['condicao']}</span>
                <span style="font-size:0.75rem; color:#CBD5E1;">💧 {wx['umidade']}% UR</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # BREAKING NEWS TICKER (Puxa a primeira matéria mais recente da aba de SP)
    artigos_sp = fetch_feed_articles(FEEDS["📍 Cotidiano Local (SP)"])
    if artigos_sp:
        ultima_hora = artigos_sp[0]
        st.markdown(f"""
        <div class="breaking-ticker">
            <span class="breaking-badge">⚡ ÚLTIMA HORA (SP)</span>
            <a href="{ultima_hora['link']}" target="_blank" class="breaking-text">{ultima_hora['titulo']} — <span style="color:#718096;">{ultima_hora['fonte']}</span></a>
        </div>
        """, unsafe_allow_html=True)

    filtro = st.text_input(
        "Pesquisar notícias...",
        placeholder="Filtrar por palavras-chave em qualquer categoria (Ex: Porsche, Ferrari, IA, Tarcísio, Hamilton, Selic...)",
        label_visibility="collapsed",
    )

    categorias = list(FEEDS.keys()) + [f"⭐ Guardados ({len(st.session_state.favoritos)})"]
    abas = st.tabs(categorias)

    for i, categoria in enumerate(FEEDS.keys()):
        with abas[i]:
            fontes = FEEDS[categoria]
            with st.spinner(f"A sincronizar {categoria}..."):
                artigos = fetch_feed_articles(fontes)

            if filtro and filtro.strip():
                termo = filtro.lower()
                artigos = [
                    a for a in artigos
                    if termo in a["titulo"].lower() or termo in a["resumo"].lower()
                ]

            if not artigos:
                st.info("Nenhuma notícia encontrada para este critério no momento.")
                continue

            colunas = st.columns(3)
            for idx, art in enumerate(artigos):
                col = colunas[idx % 3]
                with col:
                    render_article_card(art, key_prefix=f"tab_{i}")
                    st.markdown("<div style='margin-bottom: 0.6rem;'></div>", unsafe_allow_html=True)

    with abas[-1]:
        if not st.session_state.favoritos:
            st.info("Ainda não guardou nenhum artigo. Clique em '☆ Guardar' em qualquer notícia para ler mais tarde.")
        else:
            colunas_fav = st.columns(3)
            for idx, art in enumerate(st.session_state.favoritos):
                col = colunas_fav[idx % 3]
                with col:
                    render_article_card(art, key_prefix="fav_tab")
                    st.markdown("<div style='margin-bottom: 0.6rem;'></div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
