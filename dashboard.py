import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import glob

# --- CAMINHO DA PASTA DE CACHE PERSISTENTE ---
CACHE_DIR = "/var/data/cache"

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Análise de Despesas", initial_sidebar_state="expanded")

# --- ESTILOS E TEMAS ---
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass

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

# --- FUNÇÕES DE GERENCIAMENTO DE DADOS ---

def get_lista_dashboards_salvos():
    """Retorna uma lista com os nomes dos dashboards salvos na pasta de cache."""
    # Apenas verifica se o diretório existe. NUNCA tenta criá-lo.
    if not os.path.exists(CACHE_DIR):
        return []
    
    arquivos_parquet = glob.glob(os.path.join(CACHE_DIR, "*.parquet"))
    return sorted([os.path.basename(f).replace('.parquet', '') for f in arquivos_parquet])

def processar_e_salvar_planilha(arquivo_excel):
    """Processa uma planilha e a salva em um arquivo .parquet na pasta de cache."""
    try:
        # NÃO TENTA CRIAR O DIRETÓRIO AQUI. ASSUME QUE ELE EXISTE.
        
        df = pd.read_excel(arquivo_excel, engine='openpyxl')
        df.columns = [str(col).lower().strip() for col in df.columns]
        
        colunas_necessarias = ['data', 'descrição', 'tipo', 'valor', 'despesa', 'status', 'centro de custos']
        if not all(col in df.columns for col in colunas_necessarias):
            st.error(f"Erro: Colunas ausentes. Verifique se a planilha contém: {', '.join(colunas_necessarias)}.")
            return False

        nome_base = os.path.splitext(arquivo_excel.name)[0].replace(" ", "_")
        caminho_cache = os.path.join(CACHE_DIR, f"{nome_base}.parquet")

        df.rename(columns={'descrição': 'descricao', 'despesa': 'categoria', 'tipo': 'tipo_lancamento', 'centro de custos': 'centro_custo'}, inplace=True)
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df['valor_numerico'] = df['valor'].astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
        df['valor_numerico'] = pd.to_numeric(df['valor_numerico'], errors='coerce').fillna(0)
        df['valor_abs'] = df['valor_numerico']
        df['status'] = df['status'].astype(str).str.lower().str.strip()
        
        df['mes_ano'] = df['data'].dt.strftime('%Y-%m (%b)')
        mapa_meses = {
            'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr', 'May': 'Mai', 'Jun': 'Jun',
            'Jul': 'Jul', 'Aug': 'Ago', 'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'
        }
        for mes_en, mes_pt in mapa_meses.items():
            df['mes_ano'] = df['mes_ano'].str.replace(mes_en, mes_pt)

        df_despesas = df[df['tipo_lancamento'].str.lower() == 'despesa'].copy()
        df_despesas.dropna(subset=['data'], inplace=True)
        
        df_despesas.to_parquet(caminho_cache)
        return True

    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar o arquivo: {e}")
        return False

# --- O RESTO DO CÓDIGO (LÓGICA DA APLICAÇÃO) PERMANECE IDÊNTICO ---
st.title("Análise de Despesas")
st.sidebar.header("Gerenciador de Dashboards")

dashboards_salvos = get_lista_dashboards_salvos()

dashboard_selecionado = st.sidebar.selectbox(
    "Visualizar Dashboard Salvo",
    options=["Nenhum"] + dashboards_salvos,
    index=0
)

with st.sidebar.expander("Carregar Nova Planilha"):
    uploaded_file = st.file_uploader("Escolha uma planilha Excel (.xlsx)", type="xlsx")
    if uploaded_file:
        if st.button("Processar e Salvar"):
            with st.spinner("Processando e salvando dashboard..."):
                sucesso = processar_e_salvar_planilha(uploaded_file)
            if sucesso:
                st.success(f"Dashboard '{os.path.splitext(uploaded_file.name)[0]}' salvo com sucesso!")
                st.rerun()
            else:
                st.error("Falha ao salvar o dashboard.")

if dashboard_selecionado != "Nenhum":
    try:
        caminho_arquivo = os.path.join(CACHE_DIR, f"{dashboard_selecionado}.parquet")
        df = pd.read_parquet(caminho_arquivo)

        st.header(f"Analisando: {dashboard_selecionado.replace('_', ' ').title()}")
        
        if st.sidebar.button(f"Excluir Dashboard '{dashboard_selecionado}'", type="primary"):
            os.remove(caminho_arquivo)
            st.rerun()

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
        st.subheader(f"Despesas Totais (R$): {total_despesas:,.2f}")
        st.markdown("---")

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

    except FileNotFoundError:
        st.error("Arquivo do dashboard não encontrado. Ele pode ter sido excluído. Por favor, selecione outro ou carregue uma nova planilha.")
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar o dashboard: {e}")

else:
    st.info("Selecione um dashboard salvo ou carregue uma nova planilha na barra lateral.")







