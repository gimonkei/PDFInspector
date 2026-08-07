from __future__ import annotations
import os,sys
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtCore import QRectF
from PySide6.QtGui import QGuiApplication,QImage
from app.annotations.annotation_renderer import recommended_render_scale,render_annotation_image
from app.annotations.date_stamp import render_date_stamp_image
from app.annotations.render_contract import image_to_png_bytes,qrectf_to_fitz_rect

def main():
 QGuiApplication.instance() or QGuiApplication(sys.argv)
 records=[
 {"type":"check","x":100.0,"y":100.0,"size":18.0,"line_width":2.2,"color":"#dc0000"},
 {"type":"freehand","points":[[20,20],[30,40],[45,25],[60,45]],"line_width":2.0,"color":"#dc0000"},
 {"type":"date_stamp","x":80.0,"y":80.0,"size":72.0,"color":"blue","top":"松井","date":"2026.8.7","bottom":"確認"},
 {"type":"callout","x":100.0,"y":100.0,"width":180.0,"height":74.0,"leader_dx":-40.0,"leader_dy":90.0,"text":"日本語の吹き出し","font_size":11.0,"color":"#d00000","arrow_color":"#d00000","fill_color":"#fff8c6","fill_opacity":0.72,"text_color":"#000000","line_width":2.0,"corner_radius":10.0},
 {"type":"balloon","x":100.0,"y":100.0,"width":52.0,"height":52.0,"leader_dx":-45.0,"leader_dy":85.0,"text":"1","font_size":16.0,"color":"#d00000","arrow_color":"#d00000","fill_color":"#ffffff","fill_opacity":1.0,"text_color":"#d00000","line_width":2.0,"arrow_enabled":True},
 ]
 assert isinstance(render_date_stamp_image(records[2],10.0),QImage)
 for r in records:
  image,bounds=render_annotation_image(r,scale=recommended_render_scale(r))
  assert isinstance(image,QImage) and not image.isNull(),r["type"]
  assert isinstance(bounds,QRectF) and bounds.width()>0 and bounds.height()>0,r["type"]
  assert image_to_png_bytes(image).startswith(b"\x89PNG")
  assert qrectf_to_fitz_rect(bounds).width>0
 print(f"Annotation rendering smoke test passed for {len(records)} types.")
if __name__=="__main__": main()
