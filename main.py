from wordcloud import WordCloud
from PIL import Image
import streamlit as st
import os

def make_wordcloud(text):

    font_candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf"
    ]

    font_path = None

    for font in font_candidates:
        if os.path.exists(font):
            font_path = font
            break

    if font_path is None:
        st.error("한글 폰트를 찾을 수 없습니다.")
        return None

    wc = WordCloud(
        font_path=font_path,
        width=1200,
        height=700,
        background_color="white",
        max_words=150,
        collocations=False
    )

    return wc.generate(text)
