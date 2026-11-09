import streamlit as st
import edge_tts
import asyncio
import tempfile
import os
import re
from moviepy.editor import (
    AudioFileClip, TextClip, CompositeVideoClip, 
    ColorClip
)
from moviepy.audio.AudioClip import concatenate_audioclips
from moviepy.video.fx.all import fadein, fadeout
import time

# Configuração da página (mobile-friendly)
st.set_page_config(
    page_title="Gerador de Vídeos IA - PT",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Vozes em Português de Portugal
VOICE_MALE = "pt-PT-DuarteNeural"
VOICE_FEMALE = "pt-PT-RaquelNeural"


def parse_script_with_voices(text: str):
    """
    Divide o texto em segmentos com voz.
    Usa tags: [Homem], [Mulher], [Rapaz], [Rapariga], etc.
    """
    text = text.replace("[rapaz]", "[Homem]").replace("[Rapaz]", "[Homem]")
    text = text.replace("[rapariga]", "[Mulher]").replace("[Rapariga]", "[Mulher]")
    text = text.replace("[ele]", "[Homem]").replace("[Ele]", "[Homem]")
    text = text.replace("[ela]", "[Mulher]").replace("[Ela]", "[Mulher]")
    text = text.replace("[menino]", "[Homem]").replace("[Menino]", "[Homem]")
    text = text.replace("[menina]", "[Mulher]").replace("[Menina]", "[Mulher]")

    pattern = r"(\[Homem\]|\[Mulher\])"
    parts = re.split(pattern, text)
    
    segments = []
    current_voice = VOICE_MALE

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part == "[Homem]":
            current_voice = VOICE_MALE
        elif part == "[Mulher]":
            current_voice = VOICE_FEMALE
        else:
            clean = re.sub(r"\s+", " ", part).strip()
            if clean:
                segments.append({
                    "text": clean,
                    "voice": current_voice
                })
    
    if not segments:
        clean = re.sub(r"\s+", " ", text).strip()
        if clean:
            segments.append({"text": clean, "voice": VOICE_MALE})
    
    return segments


async def generate_audio_segments(segments):
    """Gera ficheiros de áudio para cada segmento"""
    audio_files = []
    
    for seg in segments:
        communicate = edge_tts.Communicate(seg["text"], seg["voice"])
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        await communicate.save(temp.name)
        audio_files.append(temp.name)
    
    return audio_files


def combine_audio(audio_files, output_path):
    """Junta todos os áudios num só ficheiro"""
    clips = [AudioFileClip(f) for f in audio_files]
    
    if len(clips) == 1:
        final_audio = clips[0]
    else:
        final_audio = concatenate_audioclips(clips)
    
    final_audio.write_audiofile(output_path, fps=44100, verbose=False, logger=None)
    
    for c in clips:
        c.close()
    for f in audio_files:
        try:
            os.unlink(f)
        except:
            pass
    
    return output_path


def create_vertical_video(audio_path, full_text, output_path):
    """
    Cria um vídeo vertical (9:16) simples e limpo com legendas + áudio.
    """
    audio = AudioFileClip(audio_path)
    duration = audio.duration
    
    w, h = 1080, 1920
    
    # Fundo escuro
    background = ColorClip(size=(w, h), color=(15, 15, 25), duration=duration)
    
    # Limpar tags do texto
    clean_text = re.sub(r"\[.*?\]", "", full_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        sentences = [clean_text]
    
    text_clips = []
    time_per_sentence = duration / max(len(sentences), 1)
    
    for i, sentence in enumerate(sentences):
        start = i * time_per_sentence
        
        try:
            txt = TextClip(
                sentence,
                fontsize=50,
                color="white",
                font="DejaVu-Sans-Bold",
                method="caption",
                size=(w - 140, None),
                align="center",
                stroke_color="black",
                stroke_width=2
            ).set_position(("center", h * 0.70)).set_start(start).set_duration(time_per_sentence)
            
            txt = fadein(txt, 0.25).fadeout(0.25)
            text_clips.append(txt)
        except Exception:
            # Fallback se TextClip falhar
            pass
    
    # Título
    try:
        title = TextClip(
            "Vídeo gerado com IA",
            fontsize=26,
            color=(180, 180, 200),
            font="DejaVu-Sans",
            method="label"
        ).set_position(("center", 70)).set_duration(duration)
        clips_list = [background, title] + text_clips
    except Exception:
        clips_list = [background] + text_clips
    
    video = CompositeVideoClip(clips_list, size=(w, h))
    video = video.set_audio(audio)
    video = video.set_duration(duration)
    
    video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=2,
        verbose=False,
        logger=None
    )
    
    audio.close()
    video.close()
    
    return output_path


def generate_video(script_text):
    if not script_text or not script_text.strip():
        st.error("Por favor escreve o texto do vídeo.")
        return None
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("A analisar o texto e as vozes...")
        progress_bar.progress(10)
        
        segments = parse_script_with_voices(script_text)
        
        if not segments:
            st.error("Não foi possível processar o texto.")
            return None
        
        status_text.text("A gerar as vozes (português de Portugal)...")
        progress_bar.progress(30)
        
        # Executar a função async
        audio_files = asyncio.run(generate_audio_segments(segments))
        
        status_text.text("A juntar o áudio...")
        progress_bar.progress(55)
        
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
        combine_audio(audio_files, temp_audio)
        
        status_text.text("A criar o vídeo vertical... (pode demorar um pouco)")
        progress_bar.progress(75)
        
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        create_vertical_video(temp_audio, script_text, temp_video)
        
        # Limpar áudio temporário
        try:
            os.unlink(temp_audio)
        except:
            pass
        
        progress_bar.progress(100)
        status_text.text("Concluído!")
        time.sleep(0.5)
        status_text.empty()
        progress_bar.empty()
        
        return temp_video
        
    except Exception as e:
        st.error(f"Ocorreu um erro: {str(e)}")
        return None


# ==================== INTERFACE ====================

st.title("🎬 Gerador de Vídeos IA")
st.markdown("### Português de Portugal • Com voz • Formato vertical")

st.markdown("""
**Como usar:**
1. Escreve o texto que queres que seja narrado.
2. Para mudar de voz no meio do vídeo, usa as tags:
   - `[Homem]` ou `[Rapaz]` → voz masculina
   - `[Mulher]` ou `[Rapariga]` → voz feminina
3. Clica em **Gerar Vídeo**
""")

with st.expander("📌 Exemplo de texto com vozes diferentes"):
    st.code("""[Homem] Olá, eu sou o João.
[Mulher] E eu sou a Maria.
[Homem] Hoje vamos falar sobre amizade.
[Mulher] É muito importante ter boas amizades na vida.
[Homem] Não te esqueças de valorizar quem está ao teu lado.""", language="text")

script = st.text_area(
    "Texto do vídeo",
    height=220,
    placeholder="Escreve aqui o que a IA deve narrar...\nExemplo:\n[Homem] Olá pessoal!\n[Mulher] Bem-vindos ao nosso vídeo."
)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    gerar = st.button("🎬 Gerar Vídeo", type="primary", use_container_width=True)

if gerar:
    with st.spinner("A processar... isto pode demorar 30 a 90 segundos"):
        video_path = generate_video(script)
    
    if video_path and os.path.exists(video_path):
        st.success("Vídeo gerado com sucesso!")
        st.video(video_path)
        
        # Botão de download
        with open(video_path, "rb") as f:
            st.download_button(
                label="⬇️ Descarregar Vídeo",
                data=f,
                file_name="video_ia_redes_sociais.mp4",
                mime="video/mp4",
                use_container_width=True
            )
        
        st.info("O vídeo está em formato vertical (9:16), pronto para TikTok, Reels e Shorts.")

st.markdown("---")
st.caption("Aplicação gratuita • Vozes: Duarte (masculina) e Raquel (feminina) — português de Portugal")
