#!/bin/python
#coding: utf-8
# +-------------------------------------------------------------------
# | system: 如意面板
# +-------------------------------------------------------------------
# | Author: lybbn
# +-------------------------------------------------------------------
# | QQ: 1042594286
# +-------------------------------------------------------------------
# | Date: 2025-03-31
# +-------------------------------------------------------------------

# ------------------------------
# 图片压缩类
# ------------------------------

import os
from io import BytesIO
import warnings

class ImageCompressor:
    def __init__(self):
        # 检查并安装 Pillow 库
        self._check_and_install_pillow()
        # 设置最大图片尺寸限制 (50MB)
        self.MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB
        # 允许加载大图片
        self.ImageFile.LOAD_TRUNCATED_IMAGES = True
        # 忽略 PIL 的 DecompressionBombWarning 警告
        warnings.simplefilter('ignore', self.Image.DecompressionBombWarning)

    def _check_and_install_pillow(self):
        """检查并安装 Pillow 库"""
        try:
            from PIL import Image, ImageFile
            self.Image = Image
            self.ImageFile = ImageFile
        except ImportError:
            print("Pillow 库未安装，正在尝试自动安装...")
            try:
                from utils.common import get_python_pip
                import subprocess
                _pip = get_python_pip()['pip']
                subprocess.check_call([_pip, "install", "pillow"])
                from PIL import Image, ImageFile
                self.Image = Image
                self.ImageFile = ImageFile
                print("Pillow 库安装成功!")
            except Exception as e:
                raise ImportError(f"无法自动安装 Pillow 库: {str(e)}")
    
    def compress_image(self, input_path, output_path, mode='lossy', quality=85, size=(200, 200), maintain_size=True, optimize=True):
        """
        @author:lybbn
        @name:压缩图片
        
        参数:
            input_path (str): 输入图片路径
            output_path (str): 输出图片路径
            mode (str): 压缩模式 ('lossy', 'lossless', 'advanced')
            quality (int): 图片质量 (1-100), 仅在advanced模式下使用
            size (tuple): 目标尺寸 (width, height), 如果maintain_size为False则使用
            maintain_size (bool): 是否保持原始尺寸
            optimize (bool): 是否优化图片
            
        返回:
            bool: 压缩是否成功
        """
        try:
            input_file_size = os.path.getsize(input_path)
            # 检查输入文件大小
            if input_file_size > self.MAX_IMAGE_SIZE:
                raise ValueError(f"图片大小超过限制 (最大 {self.MAX_IMAGE_SIZE//1024//1024}MB)")
            
            # 打开图片
            with self.Image.open(input_path) as img:
                # 转换模式为RGB (避免RGBA问题)
                if img.mode in ('RGBA', 'LA'):
                    img = img.convert('RGB')
                
                # 处理图片大小
                if not maintain_size:
                    img.thumbnail(size, self.Image.LANCZOS)
                
                # 根据模式设置压缩参数
                kwargs = {}
                ext = os.path.splitext(output_path)[1].lower()
                
                if mode == 'lossless':
                    if ext in ('.jpg', '.jpeg'):
                        kwargs = {'quality': 100, 'optimize': True, 'progressive': True}
                    elif ext == '.png':
                        kwargs = {'compress_level': 9, 'optimize': True}
                    elif ext == '.gif':
                        kwargs = {'optimize': True, 'save_all': True}
                elif mode == 'advanced':
                    if ext in ('.jpg', '.jpeg'):
                        kwargs = {'quality': quality, 'optimize': optimize}
                    elif ext == '.png':
                        # PNG quality 参数不同，需要转换
                        png_quality = max(1, min(quality // 10, 9))
                        kwargs = {'compress_level': 9 - png_quality, 'optimize': optimize}
                    elif ext == '.gif':
                        kwargs = {'optimize': optimize, 'save_all': True}
                else:  # lossy 默认模式
                    if ext in ('.jpg', '.jpeg'):
                        kwargs = {'quality': 75, 'optimize': optimize}
                    elif ext == '.png':
                        kwargs = {'compress_level': 9, 'optimize': optimize}
                    elif ext == '.gif':
                        kwargs = {'optimize': optimize, 'save_all': True}
                
                # 特殊处理GIF
                if ext == '.gif' and img.is_animated:
                    frames = []
                    try:
                        while True:
                            frame = img.copy()
                            if not maintain_size:
                                frame.thumbnail(size, self.Image.LANCZOS)
                            frames.append(frame)
                            img.seek(img.tell() + 1)
                    except EOFError:
                        pass
                    
                    if frames:
                        frames[0].save(
                            output_path,
                            save_all=True,
                            append_images=frames[1:],
                            loop=0,
                            **kwargs
                        )
                else:
                    # 保存图片
                    img.save(output_path, **kwargs)
                
                output_path_size = os.path.getsize(output_path)
                
                if output_path_size >= input_file_size:
                    os.remove(output_path)
                    raise ValueError("压缩后图片超过原图大小")
                
                return True
        
        except Exception as e:
            print(f"图片压缩失败: {str(e)}")
            return False
    
    def compress_image_in_memory(self, image_bytes, mode='lossy', quality=85, size=(200, 200), maintain_size=True, optimize=True):
        """
        @author:lybbn
        @name:在内存中压缩图片
        
        参数:
            image_bytes (bytes): 原始图片字节
            mode (str): 压缩模式 ('lossy', 'lossless', 'advanced')
            quality (int): 图片质量 (1-100), 仅在advanced模式下使用
            size (tuple): 目标尺寸 (width, height), 如果maintain_size为False则使用
            maintain_size (bool): 是否保持原始尺寸
            optimize (bool): 是否优化图片
            
        返回:
            bytes: 压缩后的图片字节
        """
        try:
            # 检查输入大小
            if len(image_bytes) > self.MAX_IMAGE_SIZE:
                raise ValueError(f"图片大小超过限制 (最大 {self.MAX_IMAGE_SIZE//1024//1024}MB)")
            
            # 从字节打开图片
            img = self.Image.open(BytesIO(image_bytes))
            
            # 转换模式为RGB (避免RGBA问题)
            if img.mode in ('RGBA', 'LA'):
                img = img.convert('RGB')
            
            # 处理图片大小
            if not maintain_size:
                img.thumbnail(size, self.Image.LANCZOS)
            
            # 确定输出格式 (与输入相同)
            output_format = img.format
            
            # 根据模式设置压缩参数
            kwargs = {}
            
            if mode == 'lossless':
                if output_format in ('JPEG', 'JPG'):
                    kwargs = {'quality': 100, 'optimize': True, 'progressive': True}
                elif output_format == 'PNG':
                    kwargs = {'compress_level': 9, 'optimize': True}
                elif output_format == 'GIF':
                    kwargs = {'optimize': True, 'save_all': True}
            elif mode == 'advanced':
                if output_format in ('JPEG', 'JPG'):
                    kwargs = {'quality': quality, 'optimize': optimize}
                elif output_format == 'PNG':
                    # PNG quality 参数不同，需要转换
                    png_quality = max(1, min(quality // 10, 9))
                    kwargs = {'compress_level': 9 - png_quality, 'optimize': optimize}
                elif output_format == 'GIF':
                    kwargs = {'optimize': optimize, 'save_all': True}
            else:  # lossy 默认模式
                if output_format in ('JPEG', 'JPG'):
                    kwargs = {'quality': 75, 'optimize': optimize}
                elif output_format == 'PNG':
                    kwargs = {'compress_level': 6, 'optimize': optimize}
                elif output_format == 'GIF':
                    kwargs = {'optimize': optimize, 'save_all': True}
            
            # 准备输出字节流
            output_buffer = BytesIO()
            
            # 特殊处理GIF
            if output_format == 'GIF' and img.is_animated:
                frames = []
                try:
                    while True:
                        frame = img.copy()
                        if not maintain_size:
                            frame.thumbnail(size, self.Image.LANCZOS)
                        frames.append(frame)
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
                
                if frames:
                    frames[0].save(
                        output_buffer,
                        format=output_format,
                        save_all=True,
                        append_images=frames[1:],
                        loop=0,
                        **kwargs
                    )
            else:
                # 保存图片到内存
                img.save(output_buffer, format=output_format, **kwargs)
            
            # 检查输出大小
            compressed_bytes = output_buffer.getvalue()
            if len(compressed_bytes) > self.MAX_IMAGE_SIZE:
                raise ValueError("压缩后图片仍然超过大小限制")
            
            return compressed_bytes
        
        except Exception as e:
            print(f"图片压缩失败: {str(e)}")
            return None
        

#example

# # 创建压缩器实例
# compressor = ImageCompressor()

# # 示例1: 有损压缩 (默认)
# compressor.compress_image('input.jpg', 'output_lossy.jpg')

# # 示例2: 无损压缩
# compressor.compress_image('input.png', 'output_lossless.png', mode='lossless')

# # 示例3: 高级模式 (质量80)，调整大小为300x300
# compressor.compress_image(
#     'input.gif', 
#     'output_advanced.gif', 
#     mode='advanced', 
#     quality=80, 
#     size=(300, 300),
#     maintain_size=False
# )

# # 示例4: 在内存中压缩
# with open('input.jpg', 'rb') as f:
#     image_data = f.read()
# compressed_data = compressor.compress_image_in_memory(
#     image_data, 
#     mode='advanced', 
#     quality=90
# )
# if compressed_data:
#     with open('output_memory.jpg', 'wb') as f:
#         f.write(compressed_data)