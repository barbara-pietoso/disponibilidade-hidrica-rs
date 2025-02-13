import streamlit as st
import folium
import geopandas as gpd
from shapely.geometry import Point
import requests
import zipfile
import os
import tempfile
import pandas as pd
from streamlit.components.v1 import html
from streamlit_folium import folium_static

# Configurações da página
st.set_page_config(
    page_title="Consulta de disponibilidade hídrica",
    page_icon=":droplet:",
    layout="wide"
)

col1, col2, col3 = st.columns([1,3,1])

col3.image('https://github.com/barbara-pietoso/disponibilidade-hidrica-rs/blob/main/Bras%C3%A3o---RS---Sema%20(2).png?raw=true', width=300)
col2.title('Disponibilidade Hídrica no Rio Grande do Sul')
col1.image('https://github.com/barbara-pietoso/disponibilidade-hidrica-rs/blob/main/drhslogo.png?raw=true', width=150)


# Limites aproximados de latitude e longitude do Rio Grande do Sul
LAT_MIN = -33.75  # Latitude mínima
LAT_MAX = -27.5   # Latitude máxima
LON_MIN = -54.5   # Longitude mínima
LON_MAX = -49.0   # Longitude máxima

# URL do arquivo .zip hospedado no GitHub
zip_url = "https://github.com/barbara-pietoso/balanco-hidrico/raw/main/arquivos_shape_upg.zip"

# Função para validar se as coordenadas estão dentro dos limites do Rio Grande do Sul
def valida_coordenadas(latitude, longitude):
    return LAT_MIN <= latitude <= LAT_MAX and LON_MIN <= longitude <= LON_MAX

# Layout do título no topo
#st.markdown("<h1 style='text-align: center;'>Disponibilidade Hídrica para Outorga</h1>", unsafe_allow_html=True)

# Layout de colunas para as entradas (latitude e longitude) à esquerda e o mapa à direita
col4, col5, col6 = st.columns([1,1,1])  # A primeira coluna (1) para as entradas e a segunda (2) para o mapa

# Entradas de latitude, longitude e área
with col4:
    latitude_input = st.text_input("Latitude", placeholder="Digite a latitude. Ex: -32.000")
with col5:
    longitude_input = st.text_input("Longitude", placeholder="Digite a longitude. Ex: -50.000")
with col6:
    area_input = st.text_input("Área (em km²)", placeholder="Digite a área em km²")
    
enviar = st.button("Consultar disponibilidade hídrica")

col8, col9, col10 = st.columns([1,1,1])

# Inicializar o mapa centralizado no Rio Grande do Sul
with col10:
    mapa = folium.Map(location=[-30.0, -52.5], zoom_start=5.5)

# Adicionar a funcionalidade de mostrar as coordenadas ao mover o mouse
folium.LatLngPopup().add_to(mapa)

# Lógica para exibição do mapa e consulta dos dados
if enviar:
    try:
        # Tentar converter os valores inseridos para float
        latitude = float(latitude_input)
        longitude = float(longitude_input)
        area = float(area_input)

        if valida_coordenadas(latitude, longitude):
            try:
                # Criar um mapa centralizado nas coordenadas inseridas
                mapa = folium.Map(location=[latitude, longitude], zoom_start=15)

                # Adicionar a funcionalidade de mostrar as coordenadas ao mover o mouse
                folium.LatLngPopup().add_to(mapa)

                # Baixar e extrair o shapefile do GitHub
                zip_file = requests.get(zip_url).content
                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = os.path.join(temp_dir, "shapefile.zip")
                    with open(zip_path, "wb") as f:
                        f.write(zip_file)

                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(temp_dir)

                    shp_file_path = os.path.join(temp_dir, "UNIDADES_BH_RS_NOVO.shp")
                    gdf = gpd.read_file(shp_file_path)

                    # Certificar-se de que o shapefile está em WGS84
                    if gdf.crs.to_string() != "EPSG:4326":
                        gdf = gdf.to_crs("EPSG:4326")

                    # Adicionar todas as unidades ao mapa em uma única cor
                    folium.GeoJson(
                        gdf,
                        style_function=lambda x: {'fillColor': '#aabec3', 'color': '#aabec3', 'weight': 1, 'fillOpacity': 0.4}
                    ).add_to(mapa)

                    # Criar um ponto para as coordenadas inseridas
                    ponto = Point(longitude, latitude)

                    # Adicionar o ponto ao mapa
                    folium.Marker([latitude, longitude], popup="Coordenadas Inseridas").add_to(mapa)

                    # Destacar a unidade que contém o ponto e exibir a UPG
                    unidade_encontrada = None
                    for _, row in gdf.iterrows():
                        if row['geometry'].contains(ponto):
                            # Destacar a unidade
                            folium.GeoJson(
                                row['geometry'].__geo_interface__,
                                style_function=lambda x: {'fillColor': '#117ca2', 'color': '#117ca2', 'weight': 2, 'fillOpacity': 0.3}
                            ).add_to(mapa)
                            unidade_encontrada = row['ID_Balanco']
                            break

                    if unidade_encontrada:
                        # Carregar a planilha para fazer o cruzamento com a coluna ID_Balanco
                        tabela_path = "tabela_id_balanco (1).xlsx"  # Caminho para a planilha
                        tabela_df = pd.read_excel(tabela_path)

                        # Procurar o valor correspondente à unidade
                        unidade_data = tabela_df[tabela_df['ID_Balanco'] == unidade_encontrada]

                        if not unidade_data.empty:
                            area_qesp_rio = unidade_data['area_qesp_rio'].values[0]
                            area_drenagem = unidade_data['Área de drenagem (km²)'].values[0] # Área de drenagem da unidade
                            qesp_rio = unidade_data ['Qesp_rio'].values[0] #valor da coluna Qesp_rio
                            id_balanco_utilizado = unidade_data['ID_Balanco'].values[0]  # Nome da ID_Balanco
                            upg = unidade_data['Unidade de Planejamento e Gestão'].values[0]
                            percentual_outorgavel = unidade_data['Percentual outorgável'].values[0] / 100  # Convertendo para decimal
                            padrao_ref = unidade_data['Padrão da Vazão de Referência'].values[0]
                            cod_bacia = unidade_data['COD'].values[0]
                            nome_bacia = unidade_data['Bacia Hidrográfica'].values[0]

                            # Inicializar variável para rastrear qual valor foi usado
                            origem_qesp_valor = ""

                            #Verificar se a coluna Qesp_rio está vazia
                            if pd.isna(qesp_rio):
                                # "Qesp_rio" está vazia, verificar valor de "area"
                                if area > 10:
                                    qesp_valor = unidade_data['Qesp_maior10'].values[0]
                                    origem_qesp_valor = "Qesp_maior10"
                                else:
                                    qesp_valor = unidade_data['Qesp_menor10'].values[0]
                                    origem_qesp_valor = "Qesp_menor10"
                            else:
                                 # "Qesp_rio" não está vazia, verificar relação entre "area" e "area_qesp_rio"
                                if area > area_qesp_rio:
                                    qesp_valor = qesp_rio
                                    origem_qesp_valor = "Qesp_rio"
                                else:
                                    if area > 10:
                                        qesp_valor = unidade_data['Qesp_maior10'].values[0]
                                        origem_qesp_valor = "Qesp_maior10"
                                    else:
                                        qesp_valor = unidade_data['Qesp_menor10'].values[0]
                                        origem_qesp_valor = "Qesp_menor10"

                            # Cálculo do valor em m³/s
                            valor_m3_s = qesp_valor * area
                            vazao_out = valor_m3_s * percentual_outorgavel 

                            with col8:
                                with st.container(border=True):
                                    st.metric("Bacia Hidrográfica:", f"{cod_bacia} - {nome_bacia}")
                            with col8:
                                with st.container(border=True):
                                    st.metric("Unidade de Planejamento e Gestão:", upg)
                            with col8:
                                with st.container(border=True):
                                    st.metric("Padrão da Vazão de Referência:", padrao_ref)
                            with col8:
                                with st.container(border=True):
                                    st.metric("Percentual outorgável:", f"{(percentual_outorgavel * 100):.0f}".replace('.', ',') + "%")
                            
                            with col9:
                                with st.container(border=True):
                                    st.metric("Vazão específica do local:", f"{qesp_valor:.5f}".replace('.', ',') + " m³/s/km²")
                                    st.markdown(f'<p style="text-align:left; font-size:1.5em; color:black;">({(qesp_valor * 1000):.2f}'.replace('.', ',') + ' L/s/km²)</p>', unsafe_allow_html=True)
                            

                            with col9:
                                with st.container(border=True):
                                    st.metric("Vazão de referência para sua localidade é:", f"{valor_m3_s:.6f}".replace('.', ',') + " m³/s")
                                    st.markdown(f'<p style="text-align:left; font-size:1.5em; color:black;">({(valor_m3_s * 1000):.2f}'.replace('.', ',') + ' L/s)</p>', unsafe_allow_html=True)
                            

                            with col9:
                                with st.container(border=True):
                                    st.metric("Vazão outorgável:", f"{vazao_out:.6f}".replace('.', ',') + " m³/s")
                                    st.markdown(f'<p style="text-align:left; font-size:1.5em; color:black;">({(vazao_out * 1000):.2f}'.replace('.', ',') + ' L/s)</p>', unsafe_allow_html=True)

                            # Adicionar um marcador com popup contendo 'upg'
                            folium.Marker(
                                location=[latitude, longitude],
                                popup=f"UPG: {upg}"
                            ).add_to(mapa)
                        else:
                            col4.warning("ID_Balanco não encontrado na planilha.")
                    else:
                        col4.warning("Não foi possível encontrar uma unidade correspondente à coordenada inserida.")
            except Exception as e:
                col4.error(f"Erro ao carregar o shapefile: {e}")
        else:
            col4.warning("As coordenadas estão fora dos limites do Rio Grande do Sul.")
    except ValueError:
        col4.error("Por favor, insira valores numéricos válidos para latitude, longitude e área.")

# Renderizar o mapa no Streamlit 
with col10:
    folium_static(mapa, width=600, height=450)  # Renderiza o mapa na segunda coluna
