import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import locale
import os # Importa a biblioteca para interagir com o sistema de arquivos

# --- NOME DO ARQUIVO DE CACHE ---
CACHE_FILE = "dados_cache.parquet"

# --- CONFIGURAÇÃO DO LOCALE PARA PORTUGUÊS DO BRASIL ---
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    st.warning("Locale 'pt_BR.UTF-8' não encontrado. As datas podem aparecer em inglês.")

# --- CONFIGURAÇÃO DA PÁGINA E ESTILOS ---
st.set_page_config(layout="wide", page_title="Análise de Despesas", initial_sidebar_state="expanded")

def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Arquivo de estilo '{file_name}' não encontrado.")

local_css("style.css")

def criar_tema_minimalista():
    return go.Layout(
        font=dict(family="sans-serif", size=12, color="#FAFAFA"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
        legend=dict(font=dict(color="#FAFAFA")),
        title=dict(font=dict(size=16, color="#FAFAFA"), x=0.05)
    )

plotly_template = criar_tema_minimalista()

# --- FUNÇÃO DE PROCESSAMENTO DE DADOS ---
# O decorador @st.cache_data ainda é útil para processamento em memória
@st.cache_data
def processar_dados(arquivo_excel):
    try:
        df = pd.read_excel(arquivo_excel, engine='openpyxl')
        df.columns = [str(col).lower().strip() for col in df.columns]
        
        colunas_necessarias = ['data', 'descrição', 'tipo', 'valor', 'despesa', 'status', 'centro de custos']
        if not all(col in df.columns for col in colunas_necessarias):
            st.error(f"Erro: Colunas ausentes. Verifique se a planilha contém: {', '.join(colunas_necessarias)}.")
            return None

        df.rename(columns={'descrição': 'descricao', 'despesa': 'categoria', 'tipo': 'tipo_lancamento', 'centro de custos': 'centro_custo'}, inplace=True)
        
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df['valor_numerico'] = df['valor'].astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
        df['valor_numerico'] = pd.to_numeric(df['valor_numerico'], errors='coerce').fillna(0)
        df['valor_abs'] = df['valor_numerico']
        df['status'] = df['status'].astype(str).str.lower().str.strip()
        df['mes_ano'] = df['data'].dt.strftime('%Y-%m (%b)').str.capitalize()
        
        df_despesas = df[df['tipo_lancamento'].str.lower() == 'despesa'].copy()
        df_despesas.dropna(subset=['data'], inplace=True)
        
        # --- SALVA OS DADOS PROCESSADOS NO CACHE ---
        df_despesas.to_parquet(CACHE_FILE)
        
        return df_despesas[['data', 'descricao', 'categoria', 'valor_abs', 'status', 'mes_ano', 'centro_custo']]
        
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar o arquivo: {e}")
        return None

# --- LÓGICA PRINCIPAL DA APLICAÇÃO ---
st.title("Análise de Despesas")

# Verifica se o arquivo de cache existe
if os.path.exists(CACHE_FILE):
    # Se existe, carrega os dados diretamente do cache
    df = pd.read_parquet(CACHE_FILE)
    st.session_state.df_processado = df
else:
    # Se não existe, prepara para o upload
    st.session_state.df_processado = None

# Botão para limpar o cache e carregar novos dados
if st.sidebar.button("Carregar Nova Planilha", type="primary"):
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE) # Apaga o arquivo de cache
    st.session_state.df_processado = None
    st.rerun() # Reinicia o script para mostrar a tela de upload

# --- EXIBIÇÃO DO DASHBOARD OU DA TELA DE UPLOAD ---
if st.session_state.df_processado is None:
    # TELA DE UPLOAD
    st.header("Carregar Planilha")
    uploaded_file = st.file_uploader("Escolha uma planilha Excel com o formato padrão (.xlsx)", type="xlsx", label_visibility="collapsed")

    if uploaded_file is not None:
        with st.spinner("Processando e salvando dados..."):
            processar_dados(uploaded_file)
        st.rerun() # Reinicia o script para carregar os dados do cache recém-criado
else:
    # TELA DO DASHBOARD
    df = st.session_state.df_processado

    st.sidebar.header("Filtros")
    categorias = ['Todas'] + sorted(df['categoria'].dropna().unique().tolist())
    categoria_selecionada = st.sidebar.multiselect("Categoria", categorias, default=['Todas'])
    
    status_opcoes = ['Todos'] + sorted(df['status'].dropna().unique().tolist())
    status_selecionado = st.sidebar.selectbox("Status", status_opcoes)
    
    centros_custo = ['Todos'] + sorted(df['centro_custo'].dropna().astype(str).unique().tolist())
    centro_custo_selecionado = st.sidebar.multiselect("Centro de Custo", centros_custo, default=['Todos'])

    df_filtrado = df.copy()
    if 'Todas' not in categoria_selecionada: df_filtrado = df_filtrado[df_filtrado['categoria'].isin(categoria_selecionada)]
    if status_selecionado != 'Todos': df_filtrado = df_filtrado[df_filtrado['status'] == status_selecionado]
    if 'Todos' not in centro_custo_selecionado: df_filtrado = df_filtrado[df_filtrado['centro_custo'].isin(centro_custo_selecionado)]

    total_despesas = df_filtrado['valor_abs'].sum()
    st.header(f"Despesas Totais (R$): {total_despesas:,.2f}")
    st.markdown("---")

    # (O código dos gráficos permanece o mesmo)
    row1_col1, row1_col2 = st.columns([3, 1])
    row2_col1, row2_col2 = st.columns([2, 2])
    
    with row1_col1:
        evolucao_mensal = df_filtrado.groupby('mes_ano', sort=False)['valor_abs'].sum().reset_index()
        if not evolucao_mensal.empty:
            fig = px.bar(evolucao_mensal, x='mes_ano', y='valor_abs', title="<b>Evolução Mensal das Despesas</b>", labels={'mes_ano': 'Mês/Ano', 'valor_abs': 'Valor (R$)'})
            fig.update_layout(plotly_template, yaxis_showticklabels=True, xaxis_showticklabels=True)
            fig.update_traces(marker_color='#FF8C69')
            st.plotly_chart(fig, use_container_width=True)

    with row1_col2:
        proporcao_valor = df_filtrado.groupby('status')['valor_abs'].sum()
        if not proporcao_valor.empty:
            fig = px.pie(proporcao_valor, values='valor_abs', names=proporcao_valor.index, hole=0.7, title="<b>Proporção por Status</b>", color=proporcao_valor.index, color_discrete_map={'pago': '#2ca02c', 'não pago': '#d62728', 'em aberto': '#ff7f0e'}, labels={'valor_abs': 'Valor', 'index': 'Status'})
            fig.update_layout(plotly_template, showlegend=True)
            fig.update_traces(textinfo='percent', textfont_size=16)
            st.plotly_chart(fig, use_container_width=True)

    with row2_col1:
        top_categorias = df_filtrado.groupby('categoria')['valor_abs'].sum().nlargest(10).sort_values(ascending=False)
        if not top_categorias.empty:
            fig = px.bar(top_categorias, x=top_categorias.index, y=top_categorias.values, title="<b>Top 10 Categorias</b>", labels={'index': 'Categoria', 'y': 'Valor (R$)'})
            fig.update_layout(plotly_template, xaxis_showticklabels=True, yaxis_showticklabels=True)
            fig.update_traces(marker_color='#2ca02c')
            st.plotly_chart(fig, use_container_width=True)

    with row2_col2:
        top_centros_custo = df_filtrado.dropna(subset=['centro_custo']).groupby('centro_custo')['valor_abs'].sum().nlargest(10).sort_values()
        if not top_centros_custo.empty:
            fig = px.bar(top_centros_custo, x=top_centros_custo.values, y=top_centros_custo.index, orientation='h', title="<b>Principais Centros de Custo</b>", labels={'y': 'Centro de Custo', 'x': 'Valor (R$)'})
            fig.update_layout(plotly_template, xaxis_showticklabels=True, yaxis_showticklabels=True)
            fig.update_traces(marker_color='#1f77b4')
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Lançamentos Detalhados")
    st.dataframe(df_filtrado, use_container_width=True)









