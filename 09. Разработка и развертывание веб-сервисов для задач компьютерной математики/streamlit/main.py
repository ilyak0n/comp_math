import os
import io
import pandas as pd
import sympy as sp
from sympy import Matrix, latex
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import pypandoc

# Инициализация FastAPI приложения
app = FastAPI(
    title="Coordinate Transformation API",
    description="Бэкенд для трансформации координат и генерации DOCX отчетов через Pandoc",
    version="1.0.0"
)

@app.get("/")
def read_root():
    """Корневой маршрут, возвращающий информацию о сервисе"""
    return {
        "message": "Coordinate Transformation API работает",
        "endpoints": {
            "/process-excel/": "Загрузка и обработка Excel-файла с генерацией отчета в формате Markdown"
        }
    }

@app.post("/process-excel/")
async def process_excel(
    file: UploadFile = File(...),
    initial_system: str = Form(...),
    final_system: str = Form(...)
):
    # Проверка формата файла
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы Excel (.xlsx, .xls)")

    # Имена для файлов
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    md_filename = f"report_{timestamp}.md"
    docx_filename = f"report_{timestamp}.docx"

    try:
        # Чтение содержимого файла
        contents = await file.read()
        or_df = pd.read_excel(io.BytesIO(contents))

        # Проверка наличия обязательных колонок
        required_columns = {'Name', 'X', 'Y', 'Z'}
        if not required_columns.issubset(or_df.columns):
            raise HTTPException(status_code=400, detail="В Excel-файле должны быть столбцы Name, X, Y, Z")

        # Трансформация координат
        transformed_df = transform_sk(or_df, initial_system, final_system)

        # Генерация  Markdown отчета
        markdown_text = generate_markdown_report(or_df, transformed_df, initial_system, final_system)

        # Запись текста в промежуточный .md файл
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        # Конвертация .md в .docx с помощью Pandoc
        pypandoc.convert_file(md_filename, 'docx', outputfile=docx_filename)

        # Запись текста в Word файл
        with open(docx_filename, "rb") as f:
            docx_bytes = f.read()
        
        # Создание байтового объекта для хранения отчета
        output = io.BytesIO(docx_bytes)
        output.seek(0)

        # Возвращаем отчет как скачиваемый файл
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=coordinate_report.docx"}
        )

    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка на стороне сервера: {str(e)}")
        

# База данных параметров систем координат (Кавычки удалены, типы преобразованы в float)
parameters = {
    "СК-42": {
        "ΔX": 23.56,
        "ΔY": -140.86,
        "ΔZ": -79.77,
        "ωx": -0.001738,
        "ωy": -0.346441,
        "ωz": -0.794263,
        "m": -0.2274
    },
    "СК-95": {
        "ΔX": 24.46,
        "ΔY": -130.80,
        "ΔZ": -81.53,
        "ωx": -0.001738,
        "ωy": 0.003559,
        "ωz": -0.134263,
        "m": -0.2274
    },
    "ПЗ-90": {
        "ΔX": -1.443,
        "ΔY": 0.142,
        "ΔZ": 0.230,
        "ωx": -0.001738,
        "ωy": 0.003559,
        "ωz": -0.134263,
        "m": -0.2274
    },
    "ПЗ-90.02": {
        "ΔX": -0.373,
        "ΔY": 0.172,
        "ΔZ": 0.210,
        "ωx": -0.001738,
        "ωy": 0.003559,
        "ωz": -0.004263,
        "m": -0.0074
    },
    "ПЗ-90.11": {
        "ΔX": 0.000,
        "ΔY": -0.014,
        "ΔZ": 0.008,
        "ωx": 0.000562,
        "ωy": 0.000019,
        "ωz": -0.000053,
        "m": 0.0006
    },
    "WGS-84 (G1150)": {
        "ΔX": -0.013,
        "ΔY": 0.092,
        "ΔZ": 0.030,
        "ωx": -0.001738,
        "ωy": 0.003559,
        "ωz": -0.004263,
        "m": -0.0074
    },
    "ITRF-2008": {
        "ΔX": 0.003,
        "ΔY": -0.013,
        "ΔZ": 0.008,
        "ωx": 0.000543,
        "ωy": 0.000061,
        "ωz": -0.000055,
        "m": 0.0006
    },
    "СГК-2011": {
        "ΔX": 0.0,
        "ΔY": 0.0,
        "ΔZ": 0.0,
        "ωx": 0.0,
        "ωy": 0.0,
        "ωz": 0.0,
        "m": 0.0
    }
}

def transform_sk(df: pd.DataFrame, start_sk: str, end_sk: str) -> pd.DataFrame:
    # # Проверка, есть ли выбранные системы в нашей базе данных
    # if start_sk not in parameters or end_sk not in parameters:
    #     raise ValueError("Выбранная система координат не найдена в параметрах.")
        
    start_param = parameters[start_sk]
    end_param = parameters[end_sk]
    
    # Объявление символьных переменных SymPy
    x, y, z = sp.symbols('x y z')
    ΔX, ΔY, ΔZ, ωx, ωy, ωz, m = sp.symbols('ΔX ΔY ΔZ ωx ωy ωz m')

    # Перевод углов из секунд в радианы
    ωrx = (ωx / 3600) * (sp.pi / 180)
    ωry = (ωy / 3600) * (sp.pi / 180)
    ωrz = (ωz / 3600) * (sp.pi / 180)

    # Формулы прямого и обратного преобразования
    trans_to_SGK_2011 = [
        (x + ωrz * y - ωry * z) * (1 + m * 1e-6) + ΔX,
        (-ωrz * x + y + ωrx * z) * (1 + m * 1e-6) + ΔY,
        (ωry * x - ωrx * y + z) * (1 + m * 1e-6) + ΔZ
    ]

    trans_from_SGK_2011 = [
        (x - ωrz * y + ωry * z) * (1 - m * 1e-6) - ΔX,
        (ωrz * x + y - ωrx * z) * (1 - m * 1e-6) - ΔY,
        (-ωry * x + ωrx * y + z) * (1 - m * 1e-6) - ΔZ
    ]

    result = []

    # Проход по строкам датафрейма
    for _, row in df.iterrows():
        # Подстановка параметров начальной СК для перехода к СГК-2011
        args_to = {
            x: row['X'], y: row['Y'], z: row['Z'],
            ΔX: start_param['ΔX'], ΔY: start_param['ΔY'], ΔZ: start_param['ΔZ'],
            ωx: start_param['ωx'], ωy: start_param['ωy'], ωz: start_param['ωz'],
            m: start_param['m']
        }

        x_sgk = trans_to_SGK_2011[0].evalf(subs=args_to)
        y_sgk = trans_to_SGK_2011[1].evalf(subs=args_to)
        z_sgk = trans_to_SGK_2011[2].evalf(subs=args_to)

        # Подстановка параметров конечной СК для перехода из СГК-2011
        args_from = {
            x: x_sgk, y: y_sgk, z: z_sgk,
            ΔX: end_param['ΔX'], ΔY: end_param['ΔY'], ΔZ: end_param['ΔZ'],
            ωx: end_param['ωx'], ωy: end_param['ωy'], ωz: end_param['ωz'],
            m: end_param['m']
        }

        x_res = trans_from_SGK_2011[0].evalf(subs=args_from)
        y_res = trans_from_SGK_2011[1].evalf(subs=args_from)
        z_res = trans_from_SGK_2011[2].evalf(subs=args_from)

        # Запись результата в DataFrame
        result.append([row['Name'], float(x_res), float(y_res), float(z_res)])

    return pd.DataFrame(result, columns=['Name', 'X', 'Y', 'Z'])


def generate_markdown_report(or_df: pd.DataFrame, transformed_df: pd.DataFrame, initial_system: str, final_system: str) -> str:
    # Генерируем формулу в формате LaTeX с помощью SymPy (твой код)
    x_sym, y_sym, z_sym = sp.symbols('X Y Z')
    dx, dy, dz = sp.symbols(r'\Delta\ X, \Delta\ Y, \Delta\ Z')
    wx, wy, wz = sp.symbols(r'\omega_X, \omega_Y, \omega_Z')
    m_sym = sp.symbols('m')
    matrix_b = Matrix(list(sp.symbols('Xb Yb Zb'))) # В оригинале было символы строк, поправим под Matrix
    matrix_a = Matrix([x_sym, y_sym, z_sym])
    delta_vector = Matrix([dx, dy, dz])
    trasf_matrix = Matrix([
        [1, wz, -wy],
        [-wz, 1, wx],
        [wy, -wx, 1]
    ])

    formula = f"{latex(matrix_b)} = (1 + m) {latex(trasf_matrix)} {latex(matrix_a)} + {latex(delta_vector)}"

    # Строим Markdown текст
    report_content = f"# Отчет по преобразованию координат\n\n"
    report_content += f"## Введение\n\n"
    report_content += f"В этом отчете представлены результаты процесса преобразования координат с использованием предоставленной системы.\n\n"
    report_content += f"## Параметры ввода\n\n"
    report_content += f"- **Исходная таблица данных**: {or_df.shape[0]} точек\n"
    report_content += f"- **Начальная система координат**: {initial_system}\n"
    report_content += f"- **Конечная система координат**: {final_system}\n\n"
    report_content += f"## Формула преобразования\n\n"
    report_content += f"$$ {formula} $$\n\n"
    report_content += f"## Описание преобразований\n\n"
    report_content += f"{transformed_df.shape[0]} точек были успешно преобразованы из {initial_system} в {final_system}.\n\n"
    
    # Таблица сравнения
    report_content += "## Результаты преобразований\n\n"
    report_content += "| Имя точки | Исх X | Исх Y | Исх Z | Конеч X | Конеч Y | Конеч Z |\n"
    report_content += "| --- | --- | --- | --- | --- | --- | --- |\n"

    for i in range(len(or_df)):
        srt = or_df.iloc[i]
        end = transformed_df.iloc[i]
        report_content += f"| {srt['Name']} | {srt['X']:.2f} | {srt['Y']:.2f} | {srt['Z']:.2f} | {end['X']:.2f} | {end['Y']:.2f} | {end['Z']:.2f} |\n"

    report_content += f"\n## Вывод\n\n"
    report_content += "Процесс преобразования координат был успешно выполнен."

    return report_content
