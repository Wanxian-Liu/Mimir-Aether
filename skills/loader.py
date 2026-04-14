"""
MimirAether Skill Loader

动态加载和管理外部Skill模块。
"""

import os
import importlib
import logging
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Skill动态加载器
    
    支持从指定目录动态加载Skill模块。
    """
    
    def __init__(self, skills_dir: str = None):
        import os
        if skills_dir is None:
            skills_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "skills", "modules"
            )
        self.skills_dir = skills_dir
        self._loaded_modules: Dict[str, Any] = {}
        
        os.makedirs(self.skills_dir, exist_ok=True)
    
    def load_skill_from_file(self, file_path: str) -> Optional[Callable]:
        """
        从文件加载Skill
        
        Args:
            file_path: Skill文件路径
            
        Returns:
            Skill处理函数
        """
        try:
            import importlib.util
            
            spec = importlib.util.spec_from_file_location("skill_module", file_path)
            if spec is None or spec.loader is None:
                logger.error(f"Failed to load skill from {file_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找handler函数
            if hasattr(module, 'handler'):
                handler = module.handler
                self._loaded_modules[file_path] = module
                logger.info(f"Loaded skill from {file_path}")
                return handler
            elif hasattr(module, 'execute'):
                handler = module.execute
                self._loaded_modules[file_path] = module
                logger.info(f"Loaded skill from {file_path}")
                return handler
            else:
                logger.warning(f"No handler/execute found in {file_path}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load skill from {file_path}: {e}")
            return None
    
    def load_skill_from_module(self, module_name: str) -> Optional[Callable]:
        """
        从模块名加载Skill
        
        Args:
            module_name: 模块名（如 'my_skill'）
            
        Returns:
            Skill处理函数
        """
        try:
            module = importlib.import_module(module_name)
            self._loaded_modules[module_name] = module
            
            if hasattr(module, 'handler'):
                return module.handler
            elif hasattr(module, 'execute'):
                return module.execute
            else:
                logger.warning(f"No handler/execute found in module {module_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to import skill module {module_name}: {e}")
            return None
    
    def discover_skills(self) -> List[str]:
        """
        发现目录中的所有Skill文件
        
        Returns:
            Skill文件路径列表
        """
        skill_files = []
        
        if not os.path.exists(self.skills_dir):
            return skill_files
        
        for filename in os.listdir(self.skills_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                skill_files.append(os.path.join(self.skills_dir, filename))
        
        return skill_files
    
    def load_all_skills(self) -> Dict[str, Callable]:
        """
        加载所有发现的Skill
        
        Returns:
            name -> handler 的映射
        """
        results = {}
        
        for file_path in self.discover_skills():
            handler = self.load_skill_from_file(file_path)
            if handler:
                name = os.path.splitext(os.path.basename(file_path))[0]
                results[name] = handler
        
        return results
    
    def get_loaded_modules(self) -> Dict[str, Any]:
        """获取已加载的模块"""
        return self._loaded_modules.copy()


# 导出的类和函数
__all__ = [
    "SkillLoader",
]
