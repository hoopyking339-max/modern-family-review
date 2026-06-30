#!/usr/bin/env python3
"""Modern Family Review Tool - CLI entry point."""

import sys
import os
import webbrowser
from pathlib import Path

import click

from src.pdf_processor import process_pdf, get_episode_script, get_annotations_for_episode
from src.llm_organizer import process_episode
from src.web_generator import generate_site, regenerate_index, build_episode_html
from src.processing_state import StateManager
from src.config import DEFAULT_WATCH_DIR


# ---- Shared helpers ----

def _process_all_pdfs(watch_dir, output_dir, force=False):
    """Core logic for batch processing all PDFs. Used by process-all and watch commands.
    Returns (total_processed, total_failed).
    """
    watch = Path(watch_dir)
    out = Path(output_dir)

    pdfs = sorted(watch.rglob("*Modern*Family*.pdf"))
    pdfs += sorted(watch.rglob("*/*Modern*Family*.pdf"))
    seen = set()
    pdfs = [p for p in pdfs if not (str(p) in seen or seen.add(str(p)))]

    if not pdfs:
        click.echo("❌ 未找到 Modern Family PDF 文件")
        return 0, 0

    click.echo(f"📂 找到 {len(pdfs)} 个PDF文件:")
    for p in pdfs:
        click.echo(f"   {p.relative_to(watch)}")

    state = StateManager()
    state.load()
    click.echo(f"\n📊 当前进度:\n{state.summary()}")

    total_processed = 0
    total_failed = 0

    for pdf_path in pdfs:
        click.echo(f"\n{'='*60}")
        click.echo(f"📄 {pdf_path.name}")

        if not force and state.is_pdf_current(pdf_path):
            unprocessed = state.get_unprocessed(pdf_path, [])
            if not unprocessed:
                click.echo("   ✅ 全部已处理，跳过")
                continue
            click.echo(f"   📋 {len(unprocessed)} 集待处理")
        else:
            if force:
                click.echo("   🔄 强制重新处理模式")
            else:
                click.echo("   🆕 新文件或文件已更新")

        click.echo("   📖 读取PDF...")
        try:
            script_data = process_pdf(pdf_path)
        except Exception as e:
            click.echo(f"   ❌ 读取PDF失败: {e}")
            continue

        episodes = script_data.episodes
        click.echo(f"   检测到 {len(episodes)} 集")

        ep_labels = [ep.label for ep in episodes]
        ep_titles = {ep.label: getattr(ep, 'title', '') or '' for ep in episodes}
        state.register_pdf(pdf_path, ep_labels, ep_titles)

        if force:
            to_process = episodes
        else:
            unprocessed_labels = state.get_unprocessed(pdf_path, ep_labels)
            to_process = [e for e in episodes if e.label in unprocessed_labels]

        if not to_process:
            click.echo("   ✅ 全部已处理")
            continue

        click.echo(f"\n📺 将处理 {len(to_process)} 集:")
        for ep in to_process:
            click.echo(f"   {ep.label} (第{ep.start_page}-{ep.end_page}页)")

        for i, ep in enumerate(to_process, 1):
            click.echo(f"\n{'─'*50}")
            click.echo(f"🔄 [{i}/{len(to_process)}] 处理 {ep.label}...")

            script = get_episode_script(ep)
            annotations = get_annotations_for_episode(script_data, ep)

            click.echo(f"   台词长度: {len(script)} 字符")
            click.echo(f"   批注数: {len(annotations)}")

            if len(script) < 100:
                click.echo("   ⚠️ 台词太短，跳过")
                continue

            click.echo("   🤖 调用DeepSeek API分析...")
            try:
                review = process_episode(
                    episode_label=ep.label,
                    episode_title="",
                    episode_script=script,
                    annotations=annotations,
                )
                # Write episode HTML immediately
                ep_html = build_episode_html(review)
                filename = f"{ep.label.lower()}.html"
                (out / filename).write_text(ep_html, encoding="utf-8")
                # Save state + regenerate index
                state.mark_processed(pdf_path, ep.label, review.episode_title)
                all_info = state.get_all_episodes()
                regenerate_index(output_dir=out, all_episodes_info=all_info)
                total_processed += 1
                click.echo(f"   ✅ 完成! 批注知识点: {review.user_annotations_count}, AI补充: {review.ai_discoveries_count}")
            except KeyboardInterrupt:
                click.echo("\n   ⏸️  用户中断。进度已保存，下次运行从此处继续。")
                click.echo(f"\n{state.summary()}")
                return total_processed, total_failed
            except Exception as e:
                click.echo(f"   ❌ 处理失败: {e}")
                state.mark_failed(pdf_path, ep.label, str(e))
                total_failed += 1
                continue

    click.echo(f"\n{'='*60}")
    click.echo("🎉 批量处理完成!")
    click.echo(f"   成功: {total_processed} 集")
    if total_failed:
        click.echo(f"   失败: {total_failed} 集")
    click.echo(f"\n{state.summary()}")

    # Final regenerate
    all_info = state.get_all_episodes()
    out = regenerate_index(output_dir=out, all_episodes_info=all_info)
    click.echo(f"\n🌐 网站已更新: {out.absolute()}")

    return total_processed, total_failed


@click.group()
def main():
    """🎬 Modern Family · 台词批注智能复习助手"""
    pass


@main.command()
@click.option("--input", "-i", "input_path", required=True, help="PDF台词本路径")
@click.option("--episode", "-e", "episode_filter", default=None, help="指定集数 (如 S01E08)")
@click.option("--all", "-a", "process_all_flag", is_flag=True, help="处理PDF中所有集数")
@click.option("--force", "-f", "force", is_flag=True, help="强制重新处理已完成的集数")
@click.option("--output", "-o", "output_dir", default="data/output", help="输出目录")
def process(input_path, episode_filter, process_all_flag, force, output_dir):
    """处理PDF台词本，生成复习网页"""
    pdf_path = Path(input_path)
    if not pdf_path.exists():
        click.echo(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    click.echo(f"📄 读取PDF: {pdf_path.name}")
    script_data = process_pdf(pdf_path)
    click.echo(f"   总页数: {script_data.total_pages}")
    click.echo(f"   检测到 {len(script_data.episodes)} 集")
    click.echo(f"   用户批注: {len(script_data.all_annotations)} 条")

    # Filter episodes
    episodes = script_data.episodes
    if episode_filter:
        episodes = [e for e in episodes if e.label.upper() == episode_filter.upper()]
        if not episodes:
            click.echo(f"❌ 未找到集数: {episode_filter}")
            click.echo(f"   可用集数: {', '.join(e.label for e in script_data.episodes)}")
            sys.exit(1)
    elif not process_all_flag:
        # Default: process only the first episode (safe single-episode mode)
        episodes = episodes[:1]
        click.echo(f"   💡 默认处理第一集。使用 --all 处理全部 {len(script_data.episodes)} 集")

    # Check processing state for incremental mode
    state = StateManager()
    state.load()
    if not force and (process_all_flag or episode_filter is None):
        unprocessed = []
        skipped = 0
        for ep in episodes:
            if state.is_processed(pdf_path, ep.label):
                skipped += 1
            else:
                unprocessed.append(ep)
        if skipped > 0:
            click.echo(f"   ⏭️  跳过 {skipped} 集已处理 (用 --force 强制重处理)")
        episodes = unprocessed if not episode_filter else episodes  # Don't skip if explicit --episode

    if not episodes:
        click.echo("✅ 所有集数已处理完毕!")
        # Still regenerate index
        all_info = state.get_all_episodes()
        regenerate_index(output_dir=Path(output_dir), all_episodes_info=all_info)
        return

    click.echo(f"\n📺 将处理 {len(episodes)} 集:")
    for ep in episodes:
        click.echo(f"   {ep.label} (第{ep.start_page}-{ep.end_page}页)")

    reviews = []
    for i, ep in enumerate(episodes, 1):
        click.echo(f"\n{'='*50}")
        click.echo(f"🔄 [{i}/{len(episodes)}] 处理 {ep.label}...")

        # Get script and annotations
        script = get_episode_script(ep)
        annotations = get_annotations_for_episode(script_data, ep)

        click.echo(f"   台词长度: {len(script)} 字符")
        click.echo(f"   批注数: {len(annotations)}")

        if len(script) < 100:
            click.echo(f"   ⚠️ 台词太短，跳过")
            continue

        # Process through LLM
        click.echo(f"   🤖 调用DeepSeek API分析...")
        try:
            review = process_episode(
                episode_label=ep.label,
                episode_title="",
                episode_script=script,
                annotations=annotations,
            )
            reviews.append(review)
            # Save state immediately (resume support)
            state.mark_processed(pdf_path, ep.label, review.episode_title)
            # Regenerate index after each episode to show progress
            all_info = state.get_all_episodes()
            regenerate_index(output_dir=Path(output_dir), all_episodes_info=all_info)
            click.echo(f"   ✅ 完成! 批注知识点: {review.user_annotations_count}, AI补充: {review.ai_discoveries_count}")
        except Exception as e:
            click.echo(f"   ❌ 处理失败: {e}")
            state.mark_failed(pdf_path, ep.label, str(e))
            continue

    # Final site generation with all reviews
    if reviews:
        click.echo(f"\n🌐 生成完整网站...")
        all_info = state.get_all_episodes()
        out = generate_site(reviews, output_dir=Path(output_dir), all_episodes_info=all_info)
        click.echo(f"   ✅ 网站已生成: {out.absolute()}")
    else:
        click.echo("\n⚠️  本次没有新处理的集数")

    click.echo(f"\n{state.summary()}")

    # Open in browser
    out = Path(output_dir)
    index_path = out / "index.html"
    if index_path.exists():
        click.echo(f"   🌐 打开浏览器预览...")
        webbrowser.open(f"file://{index_path.absolute()}")

    click.echo(f"\n🎉 完成!")


@main.command("process-all")
@click.option("--watch-dir", "-w", "watch_dir", default=None, help="监听目录 (默认: OneDrive GoodNotes)")
@click.option("--force", "-f", "force", is_flag=True, help="强制重新处理所有集数")
@click.option("--output", "-o", "output_dir", default="data/output", help="输出目录")
def process_all(watch_dir, force, output_dir):
    """处理GoodNotes文件夹中所有Modern Family PDF的全部集数"""
    watch = watch_dir or str(DEFAULT_WATCH_DIR)
    total_processed, total_failed = _process_all_pdfs(watch, output_dir, force=force)

    if total_processed == 0 and total_failed == 0:
        click.echo("\n✅ 所有集数已是最新!")

    # Open in browser
    index_path = Path(output_dir) / "index.html"
    if index_path.exists():
        click.echo("   🌐 打开浏览器预览...")
        webbrowser.open(f"file://{index_path.absolute()}")


@main.command()
@click.option("--port", "-p", default=8080, help="HTTP端口")
@click.option("--watch-dir", "-w", "watch_dir", default=None, help="监听目录 (默认: OneDrive GoodNotes)")
@click.option("--output", "-o", "output_dir", default="data/output", help="输出目录")
def watch(watch_dir, port, output_dir):
    """启动长期运行服务：Web服务器 + 文件监听自动处理"""
    import time
    import threading
    import http.server

    watch_path = Path(watch_dir) if watch_dir else DEFAULT_WATCH_DIR
    out = Path(output_dir)

    if not out.exists() or not (out / "index.html").exists():
        click.echo("📋 首次运行，先处理所有已有PDF...")
        _process_all_pdfs(str(watch_path), output_dir)
        click.echo("")

    # ---- File watcher ----
    click.echo(f"👀 监听目录: {watch_path}")
    click.echo("   (新增或修改 PDF 时自动处理)")

    processing_lock = threading.Lock()
    pending_event = threading.Event()
    last_change_time = [0.0]

    def on_pdf_change(path_str):
        if not path_str.endswith(".pdf"):
            return
        now = time.time()
        last_change_time[0] = now
        pending_event.set()

    def watcher_loop():
        while True:
            pending_event.wait()
            pending_event.clear()
            # Debounce: wait 15 seconds after last change
            while True:
                elapsed = time.time() - last_change_time[0]
                if elapsed >= 15:
                    break
                time.sleep(0.5)
            if time.time() - last_change_time[0] < 14:
                continue

            with processing_lock:
                click.echo(f"\n📄 检测到文件变化 ({time.strftime('%H:%M:%S')})，开始处理...")
                try:
                    _process_all_pdfs(str(watch_path), output_dir)
                except Exception as e:
                    click.echo(f"   ❌ 处理出错: {e}")

    # Start watcher thread
    watcher_thread = threading.Thread(target=watcher_loop, daemon=True)
    watcher_thread.start()

    # Set up filesystem observer
    observer = None
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class PDFHandler(FileSystemEventHandler):
            def on_created(self, event):
                on_pdf_change(event.src_path)
            def on_modified(self, event):
                on_pdf_change(event.src_path)

        observer = Observer()
        observer.schedule(PDFHandler(), str(watch_path), recursive=True)
        observer.start()
        click.echo("   ✅ 文件监听已启动")
    except ImportError:
        click.echo("   ⚠️  watchdog 未安装，文件监听不可用 (pip install watchdog)")
        click.echo("   💡 手动运行 python cli.py process-all 来更新")

    # ---- HTTP Server ----
    os.chdir(str(out))
    click.echo(f"\n🌐 预览地址: http://localhost:{port}")
    click.echo("   🎬 YouTube视频搜索API已启用")
    click.echo("   📝 在iPad上批注 → OneDrive同步 → 自动处理 → 刷新页面")
    click.echo("   按 Ctrl+C 停止")

    handler = _make_handler(output_dir)
    with http.server.HTTPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            click.echo("\n👋 再见!")
            if observer:
                observer.stop()
                observer.join()


def _make_handler(output_dir):
    """Factory to create the HTTP handler with given output_dir."""
    import http.server
    import json as json_mod
    import urllib.request
    import urllib.parse
    import re
    import os
    import asyncio
    import edge_tts
    import tempfile
    import io

    out = Path(output_dir)
    ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "TxGEqnHWrfWFTfGW9XjX")

    def _generate_tts(text, voice=None):
        if ELEVENLABS_KEY:
            try:
                req = urllib.request.Request(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
                    data=json_mod.dumps({
                        "text": text,
                        "model_id": "eleven_turbo_v2_5",
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    }).encode(),
                    headers={
                        "xi-api-key": ELEVENLABS_KEY,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg",
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        return resp.read()
            except Exception:
                pass
        v = voice or "en-US-JennyNeural"
        async def _gen():
            communicate = edge_tts.Communicate(text, v)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()
        try:
            return asyncio.run(_gen())
        except Exception:
            return None

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/api/speak"):
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                text = params.get("text", [""])[0]
                voice = params.get("voice", ["en-US-JennyNeural"])[0]
                if text and len(text) < 500:
                    audio = _generate_tts(text, voice)
                    if audio:
                        self.send_response(200)
                        self.send_header("Content-Type", "audio/mpeg")
                        self.send_header("Content-Length", str(len(audio)))
                        self.send_header("Cache-Control", "public, max-age=86400")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(audio)
                        return
                    else:
                        self.send_response(500)
                        self.end_headers()
                        return
                else:
                    self.send_response(400)
                    self.end_headers()
                return

            if self.path.startswith("/api/youtube"):
                parsed = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed.query)
                query = params.get("q", [""])[0]
                if query:
                    video = self._search_youtube(query)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json_mod.dumps(video).encode())
                else:
                    self.send_response(400)
                    self.end_headers()
                return

            path = self.path.split("?")[0]
            if path == "/":
                path = "/index.html"
            file_path = out / path.lstrip("/")
            if file_path.exists() and file_path.is_file():
                self.send_response(200)
                content_type = "text/html"
                if path.endswith(".css"):
                    content_type = "text/css"
                elif path.endswith(".js"):
                    content_type = "application/javascript"
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                if path.endswith(".html"):
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()

        def _search_youtube(self, query):
            try:
                search_url = (
                    "https://www.youtube.com/results?"
                    + urllib.parse.urlencode({"search_query": query})
                )
                req = urllib.request.Request(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )
                import ssl as _ssl
                import certifi
                _ctx = _ssl.create_default_context(cafile=certifi.where())
                with urllib.request.urlopen(req, timeout=8, context=_ctx) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                video_ids = re.findall(r'{"videoId":"([^"]+)"', html)
                if not video_ids:
                    video_ids = re.findall(r'\/watch\?v=([a-zA-Z0-9_-]{11})', html)
                if video_ids:
                    seen_v = set()
                    unique_ids = []
                    for vid in video_ids:
                        if vid not in seen_v:
                            seen_v.add(vid)
                            unique_ids.append(vid)
                    first_id = unique_ids[2] if len(unique_ids) > 2 else (unique_ids[0] if unique_ids else None)
                    if first_id:
                        titles = re.findall(
                            r'"title":\{"runs":\[\{"text":"([^"]+)"\}',
                            html,
                        )
                        title = titles[0] if titles else query
                        return {
                            "videoId": first_id,
                            "title": title,
                            "embedUrl": f"https://www.youtube.com/embed/{first_id}?autoplay=0",
                        }
            except Exception:
                pass
            return {"videoId": None, "title": "", "embedUrl": None}

    return CustomHandler


@main.command()
@click.option("--port", "-p", default=8080, help="HTTP端口")
@click.option("--output", "-o", "output_dir", default="data/output", help="输出目录")
def serve(port, output_dir):
    """启动本地Web服务器预览 (含YouTube视频搜索API)"""
    import http.server
    import os as _os

    out = Path(output_dir)
    if not out.exists() or not (out / "index.html").exists():
        click.echo(f"❌ 还没有生成网站，请先运行: python cli.py process-all")
        sys.exit(1)

    _os.chdir(str(out))
    handler = _make_handler(output_dir)
    with http.server.HTTPServer(("", port), handler) as httpd:
        click.echo(f"🌐 预览地址: http://localhost:{port}")
        click.echo(f"   🎬 YouTube视频搜索API已启用")
        click.echo(f"   按 Ctrl+C 停止")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            click.echo("\n👋 再见!")


@main.command()
@click.option("--output", "-o", "output_dir", default="data/output", help="输出目录")
def deploy(output_dir):
    """部署到GitHub Pages"""
    import subprocess

    out = Path(output_dir)
    if not out.exists():
        click.echo(f"❌ 还没有生成网站")
        sys.exit(1)

    click.echo("🚀 部署到 GitHub Pages...")
    click.echo("   (需要安装 gh CLI 并登录)")

    # Check gh CLI
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        click.echo("❌ 请先安装 GitHub CLI: brew install gh")
        click.echo("   然后登录: gh auth login")
        sys.exit(1)

    # Push to gh-pages branch
    import tempfile
    import shutil

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        # Copy output files
        for f in out.iterdir():
            if f.is_file():
                shutil.copy2(f, tmppath / f.name)

        # Create CNAME or .nojekyll
        (tmppath / ".nojekyll").touch()

        # Deploy
        subprocess.run(
            ["git", "init"], cwd=tmpdir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "checkout", "-b", "gh-pages"], cwd=tmpdir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "add", "."], cwd=tmpdir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Deploy review site"], cwd=tmpdir, check=True, capture_output=True
        )

        click.echo("   下一步: 设置GitHub仓库的Pages源为gh-pages分支")
        click.echo(f"   git push origin gh-pages --force")


@main.command()
def init():
    """初始化项目配置"""
    import os

    click.echo("🎬 Modern Family Review Tool - 初始化\n")

    # Check for .env
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        click.echo("⚠️  .env 文件已存在")
        if not click.confirm("   是否覆盖?"):
            return

    api_key = click.prompt("请输入 DeepSeek API Key", hide_input=True)
    if not api_key:
        click.echo("❌ API Key 不能为空")
        return

    env_path.write_text(f"DEEPSEEK_API_KEY={api_key}\n")
    click.echo(f"✅ 配置已保存到 {env_path}")


@main.command()
def status():
    """查看处理进度"""
    from src.pdf_processor import process_pdf
    from pathlib import Path
    import glob

    # Check for PDFs in common locations
    onedrive = Path.home() / "Library/CloudStorage/OneDrive-个人/GoodNotes"

    click.echo("📊 处理进度\n")

    if onedrive.exists():
        pdfs = list(onedrive.rglob("*.pdf"))
        click.echo(f"📂 OneDrive中的PDF: {len(pdfs)} 个")
        for pdf in pdfs[:5]:
            click.echo(f"   {pdf.relative_to(onedrive)}")

    output_dir = Path("data/output")
    if output_dir.exists():
        htmls = list(output_dir.glob("*.html"))
        click.echo(f"\n🌐 已生成的复习页: {len(htmls)} 个")
        for h in htmls:
            click.echo(f"   {h.name}")
    else:
        click.echo("\n🌐 还没有生成复习页")


if __name__ == "__main__":
    import os
    main()
