import os
import uuid
import shutil
from pathlib import Path
from flask import Flask, request, render_template, send_file, after_this_request
from FarcCreater import create_spr_sel_farc, Compression

app = Flask(__name__)
UPLOAD_FOLDER = Path("temp_uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

COMPRESSION_MAP = {
    "ATI2": Compression.ATI2,
    "BC7":  Compression.BC7,
    "DXT5": Compression.DXT5,
    "RGBA": Compression.RGBA,
}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/compile", methods=["POST"])
def compile_farc():
    session_id = str(uuid.uuid4())
    work_dir = UPLOAD_FOLDER / session_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        pv_id       = int(request.form.get("pv_id", 0))
        compression = COMPRESSION_MAP.get(request.form.get("compression", "ATI2"), Compression.ATI2)
        output_name = request.form.get("output_name", f"spr_sel_pv{pv_id:03d}").strip() or f"spr_sel_pv{pv_id:03d}"

        def save_file(field_name):
            f = request.files.get(field_name)
            if f and f.filename:
                dest = work_dir / f"{field_name}.png"
                f.save(dest)
                return dest
            return None

        bg_path   = save_file("bg_path")
        jk_path   = save_file("jk_path")
        logo_path = save_file("logo_path")

        if not bg_path:
            return "Error: Background image (SONG_BG) is required.", 400

        spr_path_dict = {"bg_path": bg_path}
        spr_path_dict["jk_path"] = jk_path if jk_path else bg_path
        if logo_path:
            spr_path_dict["logo_path"] = logo_path

        create_spr_sel_farc(pv_id, spr_path_dict, work_dir, compression)

        output_file = work_dir / f"spr_sel_pv{pv_id:03d}.farc"
        if not output_file.exists():
            return "Error: Output file was not created.", 500

        if output_name != f"spr_sel_pv{pv_id:03d}":
            renamed = work_dir / f"{output_name}.farc"
            output_file.rename(renamed)
            output_file = renamed

        @after_this_request
        def cleanup(response):
            shutil.rmtree(work_dir, ignore_errors=True)
            return response

        return send_file(
            output_file,
            as_attachment=True,
            download_name=output_file.name,
            mimetype="application/octet-stream"
        )

    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        return f"Error during processing: {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True)
