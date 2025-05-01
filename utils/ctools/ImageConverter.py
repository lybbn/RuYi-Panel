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
# 图片转换类
# ------------------------------

import os
from io import BytesIO
import warnings

class ImageConverter:
    # 标准化输出格式名称
    FORMAT_MAP = {
        'jpg': 'JPEG',
        'jpeg': 'JPEG',
        'png': 'PNG',
        'gif': 'GIF',
        'webp': 'WEBP',
        'ico': 'ICO'
    }
    def __init__(self):
        self._check_and_install_pillow()
        self.MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB限制
        self.ImageFile.LOAD_TRUNCATED_IMAGES = True
        warnings.simplefilter('ignore', self.Image.DecompressionBombWarning)

    def _normalize_format(self, format_str):
        """标准化格式名称"""
        fmt = format_str.lower()
        return self.FORMAT_MAP.get(fmt, fmt.upper())
        
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
    
    def convert_image(self, input_path, output_path, output_format=None, quality=85):
        """
        转换图片格式
        
        参数:
            input_path: 输入图片路径
            output_path: 输出图片路径
            output_format: 输出格式(不区分大小写，如jpg/png/gif/ico/jpeg)
            quality: 输出质量(1-100)，仅适用于有损格式
            
        返回:
            bool: 是否转换成功
        """
        try:
            input_file_size = os.path.getsize(input_path)
            # 检查文件大小
            if input_file_size > self.MAX_IMAGE_SIZE:
                raise ValueError(f"图片超过50MB限制: {input_file_size//1024//1024}MB")

            # 确定输出格式
            if output_format is None:
                ext = os.path.splitext(output_path)[1][1:].lower()
                output_format = self._normalize_format(ext)
            else:
                output_format = self._normalize_format(output_format)
            
            # 检查支持的格式
            if output_format not in self.FORMAT_MAP.values():
                raise ValueError(f"不支持的输出格式: {output_format}")
            
            # 打开图片
            with self.Image.open(input_path) as img:
                # 转换RGBA模式
                if img.mode in ('RGBA', 'LA') and output_format == 'JPEG':
                    img = img.convert('RGB')
                
                # 特殊处理ICO格式
                if output_format == 'ICO':
                    size = min(256, img.width, img.height)
                    img = img.resize((size, size), self.Image.LANCZOS)
                
                # 保存参数设置
                save_kwargs = {}
                if output_format == 'JPEG':
                    save_kwargs = {'quality': quality, 'optimize': True}
                elif output_format == 'PNG':
                    save_kwargs['compress_level'] = min(9, 10 - quality//10)
                
                # 保存图片
                img.save(output_path, **save_kwargs)
                
                # 检查输出大小
                if os.path.getsize(output_path) > self.MAX_IMAGE_SIZE:
                    os.remove(output_path)
                    raise ValueError("转换后图片仍超过50MB限制")
                
                return True
                
        except Exception as e:
            print(f"图片转换失败: {str(e)}")
            return False
    
    def convert_image_in_memory(self, image_bytes, output_format='png', quality=85, maintain_size=True, optimize=True, size=(200, 200)):
        """
        内存中的图片格式转换
        
        参数:
            image_bytes: 原始图片字节
            output_format: 输出格式(不区分大小写，如jpg/png/gif/ico/jpeg)
            quality: 输出质量(1-100)
            maintain_size (bool): 是否保持原始尺寸
            optimize (bool): 是否优化图片
            size (tuple): 目标尺寸 (width, height), 如果maintain_size为False则使用
        返回:
            bytes: 转换后的图片字节，失败返回None
        """
        try:
            # 检查大小
            if len(image_bytes) > self.MAX_IMAGE_SIZE:
                raise ValueError(f"图片超过50MB限制: {len(image_bytes)//1024//1024}MB")
            
            #标准化输出格式名称
            output_format = self._normalize_format(output_format)
            
            # 检查支持的格式
            if output_format not in self.FORMAT_MAP.values():
                raise ValueError(f"不支持的输出格式: {output_format}")
            
            # 打开图片
            img = self.Image.open(BytesIO(image_bytes))
            
            # 处理透明背景
            if img.mode in ('RGBA', 'LA') and output_format == 'JPEG':
                img = img.convert('RGB')
            
            # 特殊处理ICO格式
            if output_format == 'ICO':
                if not maintain_size:
                    minsize = min((32,)+size)
                else:
                    minsize = min(32, img.width, img.height)
                img = img.resize((minsize, minsize), self.Image.LANCZOS)
            else:
                # 处理图片大小
                if not maintain_size:
                    # img.thumbnail(size, self.Image.LANCZOS)#等比例缩减
                    img = img.resize(size, self.Image.LANCZOS)
            
            # 保存参数设置
            save_kwargs = {'format': output_format}
            if output_format in ['JPEG','ICO','WEBP']:
                save_kwargs.update({
                    'quality': quality,
                    'optimize': optimize
                })
            elif output_format == 'PNG':
                save_kwargs['compress_level'] = min(9, 10 - quality//10)
                if img.mode == 'RGB':
                    img = img.convert('RGBA')  # 保持PNG透明度
            elif output_format == 'GIF':
                save_kwargs.update({
                    'save_all': True,
                    'optimize': optimize
                })
            
            # 保存到内存
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
                        **save_kwargs
                    )
            else:
                # 保存图片到内存
                img.save(output_buffer, **save_kwargs)
            output_bytes = output_buffer.getvalue()
            
            # 检查输出大小
            if len(output_bytes) > self.MAX_IMAGE_SIZE:
                raise ValueError("转换后图片仍超过50MB限制")
            
            return output_bytes
            
        except Exception as e:
            msg= f"内存图片转换失败: {str(e)}"
            return None
        
#example
# # 初始化转换器
# converter = ImageConverter()

# # 示例1: 将JPG转为PNG
# converter.convert_image('input.jpg', 'output.png')

# # 示例2: 将PNG转为高质量JPG
# converter.convert_image('input.png', 'output.jpg', quality=95)

# # 示例3: 将图片转为ICO图标
# converter.convert_image('logo.png', 'favicon.ico')

# # 示例4: 内存中转换
# with open('photo.jpg', 'rb') as f:
#     img_data = f.read()
# png_data = converter.convert_image_in_memory(img_data, 'png')
# if png_data:
#     with open('converted.png', 'wb') as f:
#         f.write(png_data)