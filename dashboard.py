import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Настройка страницы
st.set_page_config(page_title="Статистика Кураторов", layout="wide")

st.title("📊 Панель управления: Эффективность Кураторов")

# Подключение к БД
def load_data():
    try:
        # Используем режим uri для открытия в режиме read-only (желательно, но sqlite справляется)
        conn = sqlite3.connect('file:bot_database.db?mode=ro', uri=True)
        
        # Загружаем все сообщения
        query = """
        SELECT curator_name, message_date, message_hour, chats_count, created_at 
        FROM curator_messages
        WHERE chats_count BETWEEN 0 AND 100 -- Отсекаем служебные коды типа -1
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Преобразуем даты
        df['message_date'] = pd.to_datetime(df['message_date'])
        df['created_at'] = pd.to_datetime(df['created_at'])
        return df
    except Exception as e:
        st.error(f"Ошибка чтения базы данных: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("База данных пока пуста или не найдена.")
    st.stop()

# --- БОКОВАЯ ПАНЕЛЬ (ФИЛЬТРЫ) ---
st.sidebar.header("Фильтры")

# Фильтр по датам
min_date = df['message_date'].min().date()
max_date = df['message_date'].max().date()

date_range = st.sidebar.date_input(
    "Выберите период",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Фильтр по кураторам
all_curators = sorted(df['curator_name'].unique())
selected_curators = st.sidebar.multiselect(
    "Выберите кураторов", 
    all_curators, 
    default=all_curators
)

# --- ПРИМЕНЕНИЕ ФИЛЬТРОВ ---
mask = (
    (df['message_date'].dt.date >= date_range[0]) &
    (df['message_date'].dt.date <= date_range[1]) &
    (df['curator_name'].isin(selected_curators))
)
filtered_df = df[mask]

# --- KPI (МЕТРИКИ) ---
col1, col2, col3 = st.columns(3)
total_chats = filtered_df['chats_count'].sum()
total_hours = len(filtered_df)
avg_chats = round(filtered_df['chats_count'].mean(), 1) if total_hours > 0 else 0

col1.metric("Всего чатов", f"{total_chats:,}")
col2.metric("Отработано часов", f"{total_hours}")
col3.metric("Среднее кол-во чатов/час", f"{avg_chats}")

# --- ГРАФИКИ ---
st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Динамика по дням")
    daily_stats = filtered_df.groupby('message_date')['chats_count'].sum().reset_index()
    fig_line = px.line(daily_stats, x='message_date', y='chats_count', title='Количество чатов по дням')
    st.plotly_chart(fig_line, use_container_width=True)

with c2:
    st.subheader("Топ кураторов (по сумме чатов)")
    curator_stats = filtered_df.groupby('curator_name')['chats_count'].sum().reset_index().sort_values('chats_count', ascending=False)
    fig_bar = px.bar(curator_stats.head(15), x='chats_count', y='curator_name', orientation='h', title='Топ-15 кураторов')
    st.plotly_chart(fig_bar, use_container_width=True)

# --- ТАБЛИЦА С ДАННЫМИ ---
st.markdown("---")
st.subheader("Детальные данные")

# Кнопка для скачивания
csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Скачать отчет в CSV (для Excel)",
    data=csv,
    file_name='curator_stats.csv',
    mime='text/csv',
)

st.dataframe(filtered_df.sort_values(by=['message_date', 'message_hour'], ascending=False))