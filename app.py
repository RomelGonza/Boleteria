import sqlite3
import pytz
from datetime import datetime
import pandas as pd
import streamlit as st
from enum import Enum

class CategoriasBoleto(Enum):
    VIP = "VIP"
    REGULAR = "Regular"
    VISITANTE = "Visitante"

class SistemaBoleteria:
    def __init__(self):
        self.inicializar_bd()
        self.configurar_tema()

    def configurar_tema(self):
        st.set_page_config(page_title="Sistema de Registro de Boletos", layout="wide")
        st.markdown("""
            <style>
            .stButton>button {
                width: 100%;
                margin-bottom: 10px;
            }
            .big-text {
                font-size: 20px;
                font-weight: bold;
            }
            </style>
            """, unsafe_allow_html=True)

    def verificar_columna_existe(self, cursor, tabla, columna):
        cursor.execute(f"PRAGMA table_info({tabla})")
        columnas = cursor.fetchall()
        return any(col[1] == columna for col in columnas)

    def inicializar_bd(self):
        conn = sqlite3.connect('boletos.db')
        cursor = conn.cursor()
        
        # Verificar si la tabla existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='boletos'")
        tabla_existe = cursor.fetchone() is not None

        if not tabla_existe:
            # Si la tabla no existe, créala con todas las columnas
            cursor.execute('''
                CREATE TABLE boletos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo_boleto TEXT NOT NULL,
                    categoria TEXT NOT NULL DEFAULT 'REGULAR',
                    fecha DATE,
                    hora TIME,
                    CONSTRAINT codigo_unico UNIQUE (codigo_boleto)
                )
            ''')
        else:
            # Si la tabla existe, verifica si necesita la columna categoria
            if not self.verificar_columna_existe(cursor, 'boletos', 'categoria'):
                # Agregar la columna categoria con un valor predeterminado
                cursor.execute('ALTER TABLE boletos ADD COLUMN categoria TEXT NOT NULL DEFAULT "REGULAR"')

        conn.commit()
        conn.close()

    def validar_codigo_boleto(self, codigo):
        conn = sqlite3.connect('boletos.db')
        cursor = conn.cursor()
        cursor.execute('SELECT codigo_boleto, categoria, fecha, hora FROM boletos WHERE codigo_boleto = ?', (codigo,))
        registro = cursor.fetchone()
        conn.close()
        if registro:
            return True, f"El código {codigo} ({registro[1]}) ya fue registrado el {registro[2]} a las {registro[3]}"
        return False, ""

    def registrar_boleto(self, codigo, categoria):
        if not codigo:
            return False, "El código del boleto no puede estar vacío"

        existe, mensaje = self.validar_codigo_boleto(codigo)
        if existe:
            return False, mensaje

        try:
            # Establecer la zona horaria de Perú (UTC-5)
            peru_tz = pytz.timezone('America/Lima')

            # Obtener la hora actual en la zona horaria de Perú
            fecha_hora = datetime.now(peru_tz)

            conn = sqlite3.connect('boletos.db')
            cursor = conn.cursor()
            cursor.execute(''' 
                INSERT INTO boletos (codigo_boleto, categoria, fecha, hora)
                VALUES (?, ?, ?, ?)
            ''', (codigo, categoria, fecha_hora.strftime('%Y-%m-%d'), fecha_hora.strftime('%H:%M:%S')))
            conn.commit()
            conn.close()
            return True, f"Boleto {codigo} ({categoria}) registrado exitosamente"
        except sqlite3.Error as e:
            return False, f"Error al registrar el boleto: {e}"

    def borrar_ultimo_boleto(self):
        try:
            conn = sqlite3.connect('boletos.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT codigo_boleto, categoria FROM boletos
                WHERE id = (SELECT MAX(id) FROM boletos)
            ''')
            ultimo_registro = cursor.fetchone()
            
            if not ultimo_registro:
                conn.close()
                return False, "No hay boletos para borrar"
                
            cursor.execute('''
                DELETE FROM boletos
                WHERE id = (SELECT MAX(id) FROM boletos)
            ''')
            conn.commit()
            conn.close()
            return True, f"Último boleto ({ultimo_registro[0]} - {ultimo_registro[1]}) borrado exitosamente"
        except sqlite3.Error as e:
            return False, f"Error al borrar el último boleto: {e}"

    def obtener_ultimos_registros(self, limite=10):
        conn = sqlite3.connect('boletos.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT codigo_boleto, categoria, fecha, hora 
            FROM boletos 
            ORDER BY fecha DESC, hora DESC 
            LIMIT ?
        ''', (limite,))
        registros = cursor.fetchall()
        conn.close()
        return registros

    def obtener_estadisticas(self):
        conn = sqlite3.connect('boletos.db')
        cursor = conn.cursor()
        
        # Estadísticas por categoría
        cursor.execute('''
            SELECT categoria, COUNT(*) as total
            FROM boletos
            GROUP BY categoria
            ORDER BY total DESC
        ''')
        stats_categoria = cursor.fetchall()
        
        # Total de boletos
        cursor.execute('SELECT COUNT(*) FROM boletos')
        total_boletos = cursor.fetchone()[0]
        
        conn.close()
        return stats_categoria, total_boletos

    def exportar_excel(self):
        try:
            conn = sqlite3.connect('boletos.db')
            query = "SELECT codigo_boleto, categoria, fecha, hora FROM boletos ORDER BY fecha, hora"
            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                return False, "No hay registros para exportar"

            nombre_archivo = f"registro_boletos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            df.to_excel(nombre_archivo, index=False)
            return True, nombre_archivo
        except Exception as e:
            return False, f"Error al exportar: {e}"

def main():
    sistema = SistemaBoleteria()

    st.title("Sistema de Registro de Boletos")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Registro de Boletos")
        
        with st.form("registro_boleto", clear_on_submit=True):
            codigo_input = st.text_input("Código del Boleto").strip().upper()
            categoria_select = st.selectbox(
                "Categoría",
                [categoria.value for categoria in CategoriasBoleto]
            )
            
            col_form1, col_form2 = st.columns(2)
            submit_button = col_form1.form_submit_button("Registrar Boleto")
            borrar_button = col_form2.form_submit_button("Borrar Último Boleto")

            if submit_button and codigo_input:
                exito, mensaje = sistema.registrar_boleto(codigo_input, categoria_select)
                if exito:
                    st.success(mensaje)
                else:
                    st.error(mensaje)
            
            if borrar_button:
                exito, mensaje = sistema.borrar_ultimo_boleto()
                if exito:
                    st.success(mensaje)
                else:
                    st.warning(mensaje)

    with col2:
        st.subheader("Estadísticas")
        stats_categoria, total_boletos = sistema.obtener_estadisticas()
        
        st.metric("Total de Boletos", total_boletos)
        
        for categoria, total in stats_categoria:
            porcentaje = (total / total_boletos * 100) if total_boletos > 0 else 0
            st.metric(f"Total {categoria}", f"{total} ({porcentaje:.1f}%)")

    st.subheader("Últimos Registros")
    registros = sistema.obtener_ultimos_registros()
    if registros:
        df = pd.DataFrame(registros, columns=["Código", "Categoría", "Fecha", "Hora"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay registros para mostrar.")

    if st.button("Exportar a Excel"):
        exito, archivo = sistema.exportar_excel()
        if exito:
            with open(archivo, "rb") as file:
                st.download_button(
                    label="Descargar archivo Excel",
                    data=file,
                    file_name=archivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            st.success(f"Registros exportados exitosamente: {archivo}")
        else:
            st.error(archivo)

if __name__ == "__main__":
    main()
