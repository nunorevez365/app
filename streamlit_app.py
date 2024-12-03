import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ccxt
from decouple import config

# Configuração da API Bitget
try:
    API_KEY = config("BITGET_API_KEY")
    API_SECRET = config("BITGET_API_SECRET")
    PASSWORD = config("BITGET_PASSWORD")
except Exception as e:
    st.error(f"Erro ao carregar variáveis de ambiente: {e}")

bitget = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSWORD
})

# Função para coletar dados históricos
def coletar_dados(symbol, timeframe='1h', limit=500):
    try:
        ohlcv = bitget.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        st.error(f"Erro ao coletar dados: {e}")
        return None

# Função para identificar picos e vales mais significativos
def identificar_picos_vales(df, coluna='close', threshold=0.02):
    picos, vales = [], []
    for i in range(2, len(df) - 2):
        if df[coluna][i] > df[coluna][i - 1] and df[coluna][i] > df[coluna][i + 1] and df[coluna][i] > df[coluna][i - 2] and df[coluna][i] > df[coluna][i + 2]:
            picos.append((df['timestamp'][i], df[coluna][i]))
        elif df[coluna][i] < df[coluna][i - 1] and df[coluna][i] < df[coluna][i + 1] and df[coluna][i] < df[coluna][i - 2] and df[coluna][i] < df[coluna][i + 2]:
            vales.append((df['timestamp'][i], df[coluna][i]))
    return picos, vales

# Função para detectar as Ondas de Elliott, incluindo sub-ondas com regras ajustadas
def detectar_ondas_elliott(picos, vales):
    ondas = []
    if len(picos) < 5 or len(vales) < 5:
        return ondas

    idx = 0
    while idx + 8 < min(len(picos), len(vales)):
        # Ondas impulsivas (1, 2, 3, 4, 5)
        ondas.append({
            'tipo': '1',
            'inicio': vales[idx][0],
            'preco_inicial': vales[idx][1],
            'fim': picos[idx][0],
            'preco_final': picos[idx][1]
        })
        ondas.append({
            'tipo': '2',
            'inicio': picos[idx][0],
            'preco_inicial': picos[idx][1],
            'fim': vales[idx + 1][0],
            'preco_final': vales[idx + 1][1]
        })
        ondas.append({
            'tipo': '3',
            'inicio': vales[idx + 1][0],
            'preco_inicial': vales[idx + 1][1],
            'fim': picos[idx + 1][0],
            'preco_final': picos[idx + 1][1]
        })
        ondas.append({
            'tipo': '4',
            'inicio': picos[idx + 1][0],
            'preco_inicial': picos[idx + 1][1],
            'fim': vales[idx + 2][0],
            'preco_final': vales[idx + 2][1]
        })
        ondas.append({
            'tipo': '5',
            'inicio': vales[idx + 2][0],
            'preco_inicial': vales[idx + 2][1],
            'fim': picos[idx + 2][0],
            'preco_final': picos[idx + 2][1]
        })

        # Ondas corretivas (A, B, C)
        ondas.append({
            'tipo': 'A',
            'inicio': picos[idx + 2][0],
            'preco_inicial': picos[idx + 2][1],
            'fim': vales[idx + 3][0],
            'preco_final': vales[idx + 3][1]
        })
        ondas.append({
            'tipo': 'B',
            'inicio': vales[idx + 3][0],
            'preco_inicial': vales[idx + 3][1],
            'fim': picos[idx + 3][0],
            'preco_final': picos[idx + 3][1]
        })
        ondas.append({
            'tipo': 'C',
            'inicio': picos[idx + 3][0],
            'preco_inicial': picos[idx + 3][1],
            'fim': vales[idx + 4][0],
            'preco_final': vales[idx + 4][1]
        })

        idx += 5

    return ondas

# Função para validar e ajustar a posição das ondas, garantindo que as marcações sigam as regras de Elliott
def validar_ajustar_ondas(ondas):
    for i in range(len(ondas)):
        if ondas[i]['tipo'] == '3':
            # A onda 3 deve ser maior que a onda 1 e não deve ser a menor
            if ondas[i]['preco_final'] <= ondas[i-2]['preco_final']:
                ondas[i]['preco_final'] = ondas[i-2]['preco_final'] * 1.618

        if ondas[i]['tipo'] == '4':
            # A onda 4 não deve se sobrepor à onda 1
            if ondas[i]['preco_final'] <= ondas[i-3]['preco_inicial']:
                ondas[i]['preco_final'] = ondas[i-3]['preco_inicial'] * 1.05

        if ondas[i]['tipo'] == '5':
            # A onda 5 deve ser aproximadamente do mesmo tamanho da onda 1
            ondas[i]['preco_final'] = ondas[i-4]['preco_final'] + (ondas[i-4]['preco_final'] - ondas[i-4]['preco_inicial'])

        if ondas[i]['tipo'] in ['A', 'B', 'C']:
            # Ajuste para ondas corretivas seguindo proporções de Fibonacci
            if ondas[i]['tipo'] == 'A':
                ondas[i]['preco_final'] = ondas[i-1]['preco_final'] * 0.618
            elif ondas[i]['tipo'] == 'B':
                ondas[i]['preco_final'] = max(ondas[i-1]['preco_final'], ondas[i-2]['preco_final']) * 1.05
            elif ondas[i]['tipo'] == 'C':
                ondas[i]['preco_final'] = ondas[i-2]['preco_inicial']

        # Garantir que a onda 2 não ultrapassa 20% abaixo ou acima da onda 1
        if ondas[i]['tipo'] == '2':
            max_onda1 = ondas[i-1]['preco_inicial'] * 1.2
            min_onda1 = ondas[i-1]['preco_inicial'] * 0.8
            if ondas[i]['preco_final'] > max_onda1:
                ondas[i]['preco_final'] = max_onda1
            elif ondas[i]['preco_final'] < min_onda1:
                ondas[i]['preco_final'] = min_onda1

        # Garantir que a onda 4 não anule a onda 1
        if ondas[i]['tipo'] == '4' and ondas[i-3]['tipo'] == '1':
            if ondas[i]['preco_final'] < ondas[i-3]['preco_inicial']:
                ondas[i]['preco_final'] = ondas[i-3]['preco_inicial'] * 1.05

        # Ajuste específico para ondas corretivas (B sempre no máximo relativo)
        if ondas[i]['tipo'] == 'B':
            ondas[i]['preco_final'] = max(ondas[i]['preco_inicial'], ondas[i-1]['preco_final']) * 1.05

    return ondas

# Função para plotar o gráfico estilizado com suporte e resistência
def plotar_grafico(df, picos, vales, ondas, symbol):
    fig = go.Figure()

    # Fundo claro para maior contraste e legibilidade
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='black')
    )

    # Velas japonesas
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Velas Japonesas',
        increasing_line_color='limegreen',
        decreasing_line_color='red'
    ))

    # Ondas de Elliott (Principais e Corretivas) com Diferentes Níveis
    for idx, onda in enumerate(ondas):
        cor = 'blue' if onda['tipo'] in '12345' else 'orange'
        espessura = 2

        # Ajuste de posição para evitar sobreposição com velas
        ajuste_y = 0.05 * (df['high'].max() - df['low'].min())
        if onda['tipo'] in '135':
            y_text = df[df['timestamp'] == onda['fim']]['high'].values[0] + ajuste_y
        elif onda['tipo'] in '24ABC':
            y_text = df[df['timestamp'] == onda['fim']]['low'].values[0] - ajuste_y
        else:
            y_text = onda['preco_inicial']

        # Garantir que as etiquetas das ondas não sobreponham as velas
        if any(trace['x'] == [onda['fim']] for trace in fig.data if trace['type'] == 'scatter'):
            ajuste_y *= 1.5

        fig.add_trace(go.Scatter(
            x=[onda['fim']],
            y=[y_text],
            mode='text',
            text=onda['tipo'],
            textposition='top center' if onda['tipo'] in '135' else 'bottom center',
            textfont=dict(size=14, color=cor),
            name=f"Onda {onda['tipo']}"
        ))

    # Melhorar contraste visual e garantir clareza das ondas
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgrey')
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgrey')

    # Layout final
    fig.update_layout(
        title=f"Análise de Ondas de Elliott - {symbol}",
        xaxis_title="Tempo",
        yaxis_title="Preço",
        template="plotly_white",
        xaxis_rangeslider_visible=False
    )

    return fig

# Main App
def main():
    st.title("Análise de Ondas de Elliott - Estilo Completo com Suporte/Resistência")
    symbol = st.text_input("Digite o Ativo", "BTC/USDT")
    timeframe = st.selectbox("Escolha o Timeframe", ['1h', '4h', '1d'])
    limit = st.slider("Selecione o número de candles", 100, 1000, 500)

    df = coletar_dados(symbol, timeframe, limit)

    if df is not None and not df.empty:
        picos, vales = identificar_picos_vales(df)
        ondas = detectar_ondas_elliott(picos, vales)
        ondas = validar_ajustar_ondas(ondas)

        # Mostrar apenas estatísticas dos picos, vales, e ondas
        st.write(f"Número de picos identificados: {len(picos)}")
        st.write(f"Número de vales identificados: {len(vales)}")
        st.write(f"Número de ondas de Elliott detectadas: {len(ondas)}")

        fig = plotar_grafico(df, picos, vales, ondas, symbol)
        st.plotly_chart(fig)

if __name__ == "__main__":
    main()
