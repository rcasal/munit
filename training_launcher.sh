#!/bin/sh
python3 munit/munit.py \
   --base_data_dir "datasets/ancestor_saga/" \
   --output_dir  "munit_results" \
   --img_width 512 \
   --crop_size 512 \
   --max_iter 10000 \
   --display_size 5 \
   --save_freq 30 \
   --batch_size 2 \
   --gpus 4 \
   --experiment_name "bs4" \
   #--continue_training \
   #

