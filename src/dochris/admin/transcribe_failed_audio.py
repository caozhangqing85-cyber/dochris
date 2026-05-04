#!/usr/bin/env python3
"""
转录失败状态的音频文件（faster-whisper）
"""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 添加路径
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

# 导入 manifest 管理
from dochris.manifest import (
    get_all_manifests,
    get_default_workspace,
    get_manifest,
    update_manifest_status,
)

# 配置
WORKSPACE = Path.home() / ".openclaw/knowledge-base"
TRANSCRIPTS_DIR = WORKSPACE / "transcripts"
LOGS_PATH = WORKSPACE / "logs"


# 日志配置
def setup_logging() -> logging.Logger:
    """配置日志系统"""
    LOGS_PATH.mkdir(parents=True, exist_ok=True)

    log_file = LOGS_PATH / f"transcribe_failed_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger = logging.getLogger(__name__)
    logger.info(f"📝 日志文件: {log_file}")

    return logger


logger = setup_logging()

# 检查 faster-whisper 是否可用
try:
    from faster_whisper import WhisperModel

    FASTER_WHISPER_AVAILABLE = True
    logger.info("✅ faster-whisper 已安装")
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.error("❌ faster-whisper 未安装")
    logger.error("请安装音频处理依赖: pip install dochris[audio]")
    logger.error("或: pip install faster-whisper>=0.10.0")
    sys.exit(1)


class FasterWhisperTranscriber:
    """faster-whisper 转录器"""

    def __init__(
        self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"
    ) -> None:
        """初始化转录器"""
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

        logger.info(f"📦 加载 faster-whisper {model_size} 模型...")
        try:
            self.model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
            logger.info(f"✅ faster-whisper {model_size} 模型加载成功")
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"faster-whisper模型加载失败: {e}")
            raise

    def check_duration(
        self, file_path: Path, max_duration: int = 1800
    ) -> tuple[bool, float | None]:
        """检查音频时长"""
        import subprocess

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration > max_duration, duration
            else:
                return False, None
        except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as e:
            logger.warning(f"⚠️  无法检查音频时长: {e}")
            return False, None

    def transcribe(self, file_path: Path, src_id: str) -> tuple[str | None, str | None] | None:
        """转录音频文件，支持超长文件分段转录"""
        import subprocess

        try:
            is_video = file_path.suffix.lower() in (
                ".mp4",
                ".mkv",
                ".avi",
                ".mov",
                ".wmv",
                ".flv",
                ".webm",
                ".m4v",
            )
            actual_file = file_path

            if is_video:
                # 从视频中提取音频
                audio_tmp = file_path.with_suffix(".extracted_audio.wav")
                logger.info(f"🎬 视频文件，提取音频: {file_path.name}")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(file_path),
                        "-vn",
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        str(audio_tmp),
                    ],
                    capture_output=True,
                    timeout=300,
                )
                if audio_tmp.exists():
                    actual_file = audio_tmp
                    logger.info(f"✅ 音频提取完成: {audio_tmp.name}")
                else:
                    return None, "视频音频提取失败"

            # 检查音频时长
            is_too_long, duration = self.check_duration(actual_file)

            if is_too_long:
                # 分段转录超长文件
                if duration is not None:
                    return self._transcribe_long(actual_file, src_id, int(duration))
                else:
                    return None, "无法获取音频时长"

            logger.info(f"🎧 处理音频: {actual_file.name}")
            text = self._run_whisper(str(actual_file))

            if not text:
                return None, "转录结果为空"

            # 清理临时音频文件
            if is_video:
                try:
                    actual_file.unlink(missing_ok=True)
                except OSError as e:
                    logger.debug(f"临时文件清理跳过: {e}")

            # 保存转录文本
            TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            transcript_file = TRANSCRIPTS_DIR / f"{src_id}.txt"
            transcript_file.write_text(text, encoding="utf-8")
            logger.info(f"✓ 转录文本已保存: {transcript_file}")

            return text, file_path.stem

        except (OSError, subprocess.TimeoutExpired, RuntimeError) as e:
            logger.error(f"faster-whisper转录失败: {e}")
            raise

    def _run_whisper(self, audio_path: str) -> str:
        """调用 faster-whisper 转录"""
        segments, info = self.model.transcribe(
            audio_path, beam_size=5, vad_filter=True, language=None
        )
        text_parts = [segment.text for segment in segments]
        text = " ".join(text_parts).strip()
        logger.info(f"✅ 转录完成: {len(text)} 字符 | 语言: {info.language}")
        return text

    def _transcribe_long(self, audio_file: Path, src_id: str, duration_seconds: int) -> tuple:
        """分段转录超长音频文件（每段25分钟）"""
        import subprocess
        import tempfile

        chunk_minutes = 25
        chunk_seconds = chunk_minutes * 60
        total_chunks = (duration_seconds // chunk_seconds) + 1

        logger.info(f"📏 超长文件 ({duration_seconds // 60}分钟)，分 {total_chunks} 段转录")

        all_text = []
        tmp_dir = tempfile.mkdtemp(prefix="whisper_chunk_")

        try:
            for i in range(total_chunks):
                start = i * chunk_seconds
                end = min(start + chunk_seconds, duration_seconds)
                chunk_file = f"{tmp_dir}/chunk_{i:03d}.wav"

                # 用 ffmpeg 切割音频
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(audio_file),
                        "-ss",
                        str(start),
                        "-t",
                        str(end - start),
                        "-acodec",
                        "pcm_s16le",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        chunk_file,
                    ],
                    capture_output=True,
                    timeout=120,
                )

                if not Path(chunk_file).exists():
                    logger.warning(f"⚠️ 段 {i + 1}/{total_chunks} 切割失败")
                    continue

                logger.info(f"  [{i + 1}/{total_chunks}] 转录第 {start // 60}-{end // 60} 分钟...")

                try:
                    text = self._run_whisper(chunk_file)
                    if text:
                        all_text.append(text)
                except (RuntimeError, ValueError, OSError, TypeError) as e:
                    logger.warning(f"⚠️ 段 {i + 1}/{total_chunks} 转录失败: {e}")

                # 清理临时段文件
                try:
                    Path(chunk_file).unlink(missing_ok=True)
                except OSError as e:
                    logger.debug(f"临时段文件清理跳过: {e}")

            combined = " ".join(all_text).strip()

            if not combined:
                return None, f"超长文件转录结果为空 ({duration_seconds // 60}分钟)"

            logger.info(
                f"✅ 超长文件转录完成: {len(combined)} 字符 ({duration_seconds // 60}分钟, {total_chunks}段)"
            )

            # 保存
            TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            transcript_file = TRANSCRIPTS_DIR / f"{src_id}.txt"
            transcript_file.write_text(combined, encoding="utf-8")
            logger.info(f"✓ 转录文本已保存: {transcript_file}")

            return combined, audio_file.stem

        finally:
            # 清理临时目录
            try:
                import shutil

                shutil.rmtree(tmp_dir, ignore_errors=True)
            except OSError as e:
                logger.debug(f"临时目录清理跳过: {e}")


def get_failed_audio_manifests() -> list[dict]:
    """获取失败状态的音频和视频 manifest"""
    workspace = get_default_workspace()
    all_failed = get_all_manifests(workspace, status="failed")

    AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac", ".opus"}
    VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}

    failed_media = []
    for m in all_failed:
        src = m.get("source_path", "")
        ext = Path(src).suffix.lower() if src else ""
        if ext in AUDIO_EXTS or ext in VIDEO_EXTS:
            m["_is_video"] = ext in VIDEO_EXTS
            failed_media.append(m)

    logger.info(
        f"📊 找到失败状态的音视频文件: {len(failed_media)} 个 (视频: {sum(1 for m in failed_media if m.get('_is_video'))})"
    )

    return failed_media


def update_manifest_with_transcript(src_id: str, transcript_text: str) -> bool:
    """更新 manifest，添加转录信息"""
    workspace = get_default_workspace()
    manifest = get_manifest(workspace, src_id)

    if manifest:
        # 更新 manifest，添加转录信息
        manifest["has_transcript"] = True
        manifest["transcript_length"] = len(transcript_text)
        manifest["transcript_language"] = "auto"

        # 重置状态为 ingested，以便重新编译
        update_manifest_status(workspace, src_id, "ingested", error_message=None)

        logger.info(f"✓ Manifest 已更新: {src_id} (has_transcript=True)")
        return True

    return False


def main() -> None:
    """主函数"""
    logger.info(f"\n{'=' * 60}")
    logger.info("🚀 转录失败状态的音频文件")
    logger.info(f"{'=' * 60}\n")

    # 获取失败的音频文件
    failed_audio = get_failed_audio_manifests()

    if not failed_audio:
        logger.info("✅ 没有失败的音频文件")
        return

    # 创建转录器
    transcriber = FasterWhisperTranscriber(model_size="base", device="cuda", compute_type="int8")

    # 转录统计
    success_count = 0
    fail_count = 0
    skip_count = 0

    # 处理每个音频文件
    for i, manifest in enumerate(failed_audio, 1):
        src_id = manifest["id"]
        title = manifest.get("title", "无标题")[:50]
        file_path = WORKSPACE / manifest["file_path"]

        logger.info(f"\n[{i}/{len(failed_audio)}] {src_id}: {title}")

        if not file_path.exists():
            logger.warning(f"✗ 文件不存在: {file_path}")
            fail_count += 1
            continue

        # 转录音频
        try:
            result = transcriber.transcribe(file_path, src_id)
            if result is None:
                fail_count += 1
                logger.warning(f"⚠️  转录失败: {src_id}")
                continue
            transcript_text, audio_name = result

            if transcript_text:
                # 更新 manifest
                if update_manifest_with_transcript(src_id, transcript_text):
                    success_count += 1
                    logger.info(f"✅ 成功: {src_id}")
            else:
                # 转录失败但不是长度问题
                fail_count += 1
                logger.warning(f"⚠️  转录失败: {src_id}")

        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
            fail_count += 1
            logger.error(f"❌ 处理失败: {src_id} - {e}")

    # 打印最终报告
    logger.info(f"\n{'=' * 60}")
    logger.info("✅ 转录完成")
    logger.info(f"{'=' * 60}")
    logger.info(f"成功: {success_count} 个")
    logger.info(f"失败: {fail_count} 个")
    logger.info(f"跳过: {skip_count} 个")
    logger.info(f"总计: {len(failed_audio)} 个")

    logger.info("\n💡 下一步: 重新编译已转录的音频文件")
    logger.info(f"命令: cd {WORKSPACE} && python3 scripts/phase2_compilation.py")


if __name__ == "__main__":
    main()
