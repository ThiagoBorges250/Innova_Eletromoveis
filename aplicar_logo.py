"""Instala a logomarca escolhida no cabeçalho da Innova Eletromóveis.
Uso: python aplicar_logo.py [caminho_da_imagem]
Se o caminho não for informado, abre um seletor de arquivos.
Aceita imagens JPG, PNG, WebP, BMP; não edita o logotipo além da conversão para PNG.
"""
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
import argparse
import shutil
import sys

BASE = Path(__file__).resolve().parent
TARGET = BASE / "static" / "img" / "logo-sem-fundo.png"
BACKUP = BASE / "static" / "img" / "logo-anterior-backup.png"


def escolher_arquivo():
    try:
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selecionado = filedialog.askopenfilename(
            title="Escolha a nova logomarca da Innova",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos", "*.*")]
        )
        root.destroy()
        return selecionado
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível abrir a janela de seleção. Execute: "
            'python aplicar_logo.py "C:\\pasta\\sua-logo.png"'
        ) from exc


def aplicar(caminho):
    fonte = Path(caminho).expanduser().resolve()
    if not fonte.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {fonte}")
    if fonte == TARGET.resolve():
        print("A imagem selecionada já é a logomarca utilizada pelo site.")
        return
    try:
        with Image.open(fonte) as src:
            img = ImageOps.exif_transpose(src)
            img.load()
            if img.width < 100 or img.height < 60:
                raise ValueError("A imagem é pequena demais para uma logo nítida.")
            img = img.convert("RGBA")
            img.thumbnail((1500, 900), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Formato de imagem inválido ou arquivo danificado.") from exc
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists() and not BACKUP.exists():
        shutil.copy2(TARGET, BACKUP)
        print(f"Backup da logomarca anterior: {BACKUP}")
    temporario = TARGET.with_name("logo-nova-temporaria.png")
    try:
        img.save(temporario, "PNG", optimize=True)
        temporario.replace(TARGET)
    finally:
        temporario.unlink(missing_ok=True)
    print("[OK] Nova logo instalada em:", TARGET)
    print("Reinicie o Flask e atualize o navegador com Ctrl+Shift+R.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instala uma logomarca personalizada na Innova")
    parser.add_argument("arquivo", nargs="?", help="Caminho da imagem (opcional)")
    args = parser.parse_args()
    try:
        arquivo = args.arquivo or escolher_arquivo()
        if not arquivo:
            print("Nenhuma imagem selecionada. A logo anterior foi mantida.")
            sys.exit(0)
        aplicar(arquivo)
    except Exception as exc:
        print("[ERRO]", str(exc))
        sys.exit(1)
