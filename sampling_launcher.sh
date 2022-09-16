#!/bin/sh
python3 munit/munit_sample.py \
--base_data_dir "/home/jupyter/Ramiro/datasets/" \
--input_data_dir "character_2" \
--output_dir  "/home/jupyter/Ramiro/munit_results" \
--experiment_name "2022_09_14_15_16_gpu1"  \
--img_width 512 \
--crop_size 512 \
--output_images_subfolder_path "sampling_180" \
