import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


SOURCE_URL = "https://raw.githubusercontent.com/metaMMY07/venera-configs/addbb75180b56479375ff2a87dc167d2339778f1/"
FIXTURES = {
    "copy_manga": (
        """
const Network = { get: async () => ({
    status: 200,
    body: '{"code":200,"results":null}'
}) };
""",
        """
CopyManga.prototype.init = async function () {
    try {
        await this.comic.loadInfo("unavailable");
    } catch (error) {
        if (String(error).includes("未返回漫画详情")) {
            console.log("APPLE_SOURCE_PASS_copy_manga");
            return;
        }
        throw error;
    }
    throw "CopyManga should report an empty detail response";
};
""",
    ),
    "baozi": (
        """
const Network = { get: async (url) => ({
    status: 200,
    body: url.endsWith("_2.html")
      ? '<div class="comic-contain"><amp-img src="https://example.test/scomic/demo/1.jpg"></amp-img><amp-img src="https://example.test/scomic/demo/2.jpg"></amp-img></div>'
      : '<div class="comic-contain"><amp-img src="https://example.test/scomic/demo/1.jpg"></amp-img></div><a id="next-chapter" href="/comic/chapter/demo/0_0_2.html">下一页</a>'
}) };
""",
        """
Baozi.prototype.init = async function () {
    const { images } = await this.comic.loadEp("demo", "0");
    if (images.length !== 2 || !images[1].endsWith("/2.jpg")) {
        throw "Baozi should follow pages and preserve image order";
    }
    console.log("APPLE_SOURCE_PASS_baozi");
};
""",
    ),
    "jm": (
        """
const fetch = async () => ({ status: 503 });
const Network = { get: async () => ({ status: 503, body: "" }) };
""",
        """
const originalInit = JM.prototype.init;
JM.prototype.init = async function () {
    await originalInit.call(this);
    if (this.baseUrl !== "https://www.cdnbtd.cc") {
        throw "JM should retain its built-in API domains";
    }
    console.log("APPLE_SOURCE_PASS_jm");
};
""",
    ),
}


def wait_for(command, condition, log):
    with log.open("wb") as output:
        app = subprocess.Popen([command], stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                result = condition()
                if result:
                    return result
                if app.poll() is not None:
                    raise RuntimeError(f"Venera Next exited with code {app.returncode}")
                time.sleep(1)
            raise RuntimeError("Venera Next did not reach the expected startup state")
        finally:
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    app.kill()
                    app.wait()
            print(log.read_text(encoding="utf-8", errors="replace"))


def find_sources():
    library = Path.home() / "Library"
    roots = [
        library / "Application Support",
        library / "Containers" / "com.github.cyrilpeng.veneranext" / "Data" / "Library" / "Application Support",
    ]
    for root in roots:
        if root.exists():
            for directory in root.rglob("comic_source"):
                if directory.is_dir():
                    return directory
    return None


def main():
    command = sys.argv[1]
    directory = wait_for(command, find_sources, Path("venera-initial-start.log"))
    logfile = directory.parent / "logs.txt"

    for key, (setup, assertion) in FIXTURES.items():
        with urlopen(SOURCE_URL + key + ".js", timeout=20) as response:
            script = response.read().decode("utf-8")
        (directory / (key + ".js")).write_text(setup + script + assertion, encoding="utf-8")

    def probes_passed():
        if not logfile.is_file():
            return False
        log = logfile.read_text(encoding="utf-8", errors="replace")
        return all(f"APPLE_SOURCE_PASS_{key}" in log for key in FIXTURES)

    try:
        wait_for(command, probes_passed, Path("venera-source-start.log"))
    finally:
        if logfile.is_file():
            print(logfile.read_text(encoding="utf-8", errors="replace"))

    print("Venera Next started on macOS and all three source regression fixtures passed.")


if __name__ == "__main__":
    main()
