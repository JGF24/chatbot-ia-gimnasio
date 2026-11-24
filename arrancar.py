"""
Arranque cómodo en local: pide la clave de la API sin mostrarla en pantalla
y lanza el servidor. La clave no se guarda en ningún archivo.

Uso:  python arrancar.py
"""
import getpass
import os
import runpy
from pathlib import Path

if not os.environ.get("ANTHROPIC_API_KEY"):
    clave = getpass.getpass("Pega tu clave de API y pulsa Enter (no se vera en pantalla): ").strip()
    if not clave:
        raise SystemExit("No has escrito ninguna clave. Vuelve a ejecutar el comando.")
    if not clave.startswith("sk-ant-"):
        print("Aviso: las claves de Anthropic suelen empezar por 'sk-ant-'. Compruebala si la IA falla.")
    os.environ["ANTHROPIC_API_KEY"] = clave

os.chdir(Path(__file__).parent)
runpy.run_path("servidor.py", run_name="__main__")
