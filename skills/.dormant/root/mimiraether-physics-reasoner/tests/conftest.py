"""pytest config — inject skills/ into sys.path so mimiraether_physics_reasoner is importable"""
import sys
import os

_skills_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)
