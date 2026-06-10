import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="Трансформация координат", page_icon="🌍", layout="wide")
BACKEND_URL = "http://127.0.0.1:8000"
AVAILABLE_SYSTEMS = ["СК-42", "СК-95", "ПЗ-90", "ПЗ-90.02", "ПЗ-90.11", "WGS-84 (G1150)", "ITRF-2008", "СГК-2011"]

st.title("🌍 Автоматизированная система преобразования координат")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("⚙️ Настройки трансформации")
    initial_sk = st.selectbox("Начальная система координат", AVAILABLE_SYSTEMS, index=0)
    final_sk = st.selectbox("Конечная система координат", AVAILABLE_SYSTEMS, index=7)
    uploaded_file = st.file_uploader("Выберите Excel файл", type=['xlsx', 'xls'])

with col2:
    st.subheader("📊 Предварительный просмотр и управление")
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            required_cols = {'Name', 'X', 'Y', 'Z'}
            
            if not required_cols.issubset(df.columns):
                st.error(f"Ошибка: файл должен содержать столбцы: {', '.join(required_cols)}")
            else:
                st.dataframe(df.head(5), use_container_width=True)
                st.metric("Всего точек (строк)", df.shape[0])
                
                st.write("---")
                
                uploaded_file.seek(0)
                file_bytes = uploaded_file.read()
                
                files = {"file": (uploaded_file.name, file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                data = {"initial_system": initial_sk, "final_system": final_sk}
                
                if st.button("🚀 Запустить трансформацию и скачать DOCX"):
                    with st.spinner("Бэкенд обрабатывает координаты..."):
                        try:
                            target_url = f"{BACKEND_URL}/process-excel/"
                            response = requests.post(target_url, files=files, data=data)
                            
                            if response.status_code == 200:
                                st.success("Отчет успешно сгенерирован бэкендом!")
                                st.download_button(
                                    label="📥 Скачать готовый отчет (.docx)",
                                    data=response.content,
                                    file_name="coordinate_report.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                            else:
                                st.error(f"Ошибка сервера (Код {response.status_code}): {response.text}")
                        except Exception as e:
                            st.error(f"Не удалось связаться с бэкендом по адресу {BACKEND_URL}: {str(e)}")
                            
        except Exception as e:
            st.error(f"Ошибка чтения файла: {str(e)}")
    else:
        st.info("Пожалуйста, загрузите файл Excel в левой панели для начала работы.")
