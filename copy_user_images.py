import os
import shutil


def copy_user_images():
    """复制 user_images 目录到打包应用"""
    source_dir = 'user_images'
    target_dir = 'dist/SemanticAuthApp/user_images'

    print(f"正在将用户图片从 {source_dir} 复制到 {target_dir}...")

    # 确保源目录存在
    if not os.path.exists(source_dir):
        print(f"错误: 源目录不存在: {source_dir}")
        return False

    # 如果目标目录已存在，先删除它
    if os.path.exists(target_dir):
        print(f"目标目录已存在，正在删除: {target_dir}")
        shutil.rmtree(target_dir)

    # 复制整个目录
    try:
        shutil.copytree(source_dir, target_dir)
        print(f"✓ 成功复制 {source_dir} 到 {target_dir}")

        # 统计复制的文件夹和文件数量
        folder_count = 0
        file_count = 0
        for root, dirs, files in os.walk(target_dir):
            folder_count += len(dirs)
            file_count += len(files)

        print(f"复制了 {folder_count} 个文件夹和 {file_count} 个文件")
        return True
    except Exception as e:
        print(f"✗ 复制过程中出错: {str(e)}")
        return False


if __name__ == "__main__":
    success = copy_user_images()
    if success:
        print("\n用户图片已成功复制到打包应用中。")
        print("现在应该可以正常查看用户图片了。")
    else:
        print("\n复制用户图片失败，请检查错误信息。")