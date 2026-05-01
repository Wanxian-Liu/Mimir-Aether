import os
import sys

def create_directories():
    """创建调度系统所需的目录结构"""
    directories = [
        "mimicore/scheduler/tasks",
    ]
    
    for dir_path in directories:
        try:
            os.makedirs(dir_path, exist_ok=True)
            print(f"✓ 创建目录: {dir_path}")
        except Exception as e:
            print(f"✗ 创建目录失败 {dir_path}: {e}")
    
    # 创建 __init__.py 文件
    init_files = [
        "mimicore/__init__.py",
        "mimicore/scheduler/__init__.py",
        "mimicore/scheduler/tasks/__init__.py"
    ]
    
    for init_file in init_files:
        try:
            with open(init_file, 'w') as f:
                f.write('"""\nMimirAether 调度系统\n"""\n')
            print(f"✓ 创建文件: {init_file}")
        except Exception as e:
            print(f"✗ 创建文件失败 {init_file}: {e}")
    
    print("\n目录结构:")
    for root, dirs, files in os.walk("mimicore"):
        level = root.replace("mimicore", "").count(os.sep)
        indent = " " * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")

if __name__ == "__main__":
    create_directories()