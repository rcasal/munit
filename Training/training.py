"""File that defines the main training loop"""
import sys
import time
import torch
import torch.distributed as dist
import tensorboardX
import gc
from Data_Utils.data_utils import *
from Training.trainer import *
from Utils.util_functions import Timer, should_distribute
from Utils.reporting import write_loss, write_to_images
from tqdm import tqdm

NODES      = int(os.environ.get('WORLD_SIZE', 1))


def train(gpu,args):
    """The main training loop, give args from munit.py"""

    #multiprocessing
    args.gpu = gpu

    # Device conf, GPU and distributed computing
    torch.cuda.set_device(args.gpu)

    rank = args.nr * args.gpus + gpu

    if should_distribute(args.world_size):
        dist.init_process_group(backend=args.backend, init_method='env://', world_size=args.world_size, rank=rank)

    trainer = MUNIT_Trainer(args)

    #setup data
    train_loader_a = get_data_loader_folder(args, os.path.join(args.base_data_dir, args.input_data_dir),
        args.batch_size, True, args.img_width, args.crop_size,
        args.crop_size, args.num_workers, True, args.world_size, rank )

    train_loader_b = get_data_loader_folder(args, os.path.join(args.base_data_dir, args.style_data_dir),
        args.batch_size, True, args.img_width, args.crop_size,
        args.crop_size, args.num_workers, True, args.world_size, rank)

    model_name = args.experiment_name

    output_path = args.base_results_dir

    train_writer = tensorboardX.SummaryWriter(os.path.join(output_path + "/Loss", model_name))

    # Models to device and DDP setting
    trainer = trainer.cuda(args.gpu) 
    if is_distributed():
        trainer = nn.parallel.DistributedDataParallel(trainer, device_ids=[args.gpu])
    
    train_display_images_a = torch.stack([train_loader_a.dataset[i]
        for i in range(args.display_size)]).cuda(args.gpu)
    
    train_display_images_b = torch.stack([train_loader_b.dataset[i]
        for i in range(args.display_size)]).cuda(args.gpu)
    
    # recover from checkpoint
    iterations = 0
    if(args.continue_training and os.path.exists(args.saved_model_dir)):
        if isDDP(trainer):
            iterations = trainer.module.resume(args.saved_model_dir, args)  
        else: 
            iterations = trainer.resume(args.saved_model_dir, args)

    gc.collect()
    torch.cuda.empty_cache()
    flag_true = True
    while flag_true:
        
        start_time = time.time()
        for  (images_a, images_b) in zip(train_loader_a, train_loader_b):
            if isDDP(trainer):
                if rank == 0:
                    time_elapsed_training = time.time() - start_time
                    print(f"Iteration {(iterations + 1):08d}/{args.max_iter} completed in {(time_elapsed_training // 60):.0f}m {(time_elapsed_training % 60):.0f}s {60*time_elapsed_training % 60:.0f}ms")
                    #print(f"Iteration {(iterations + 1):08d}/{args.max_iter} completed in {(1000*time_elapsed_training)}.")
            else: 
                time_elapsed_training = time.time() - start_time
                print(f"Iteration {(iterations + 1):08d}/{args.max_iter} completed in {(time_elapsed_training // 60):.0f}m {(time_elapsed_training % 60):.0f}s {60*time_elapsed_training % 60:.0f}ms")

            
            images_a, images_b = images_a.cuda(args.gpu).detach(), images_b.cuda(args.gpu).detach()
            
            #with Timer("Elapsed time in update: %f"):
            trainer.module.dis_update(images_a, images_b, args) if isDDP(trainer) else trainer.dis_update(images_a, images_b, args)
            trainer.module.gen_update(images_a, images_b, args) if isDDP(trainer) else trainer.gen_update(images_a, images_b, args)

            # Dump training stats in log file
            if (iterations + 1) % args.print_freq == 0:
                #print(f"Iteration: {(iterations + 1):08d}/{args.max_iter}")
                #print(f"rank: {rank}")
                write_loss(iterations, trainer, train_writer)

            # Write images
            if (iterations + 1) % args.print_freq == 0:

                with torch.no_grad():
                    train_image_outputs = trainer.module.sample(train_display_images_a,train_display_images_b) if isDDP(trainer) else trainer.sample(train_display_images_a,train_display_images_b)

                write_to_images(train_image_outputs, args.display_size,
                    args.image_results_dir, f'train_{(iterations+1)}')

            # Save network weights
            if (iterations + 1) % args.save_freq == 0:
                if isDDP(trainer):
                    if rank == 0:
                        # All processes should see same parameters as they all start from same
                        # random parameters and gradients are synchronized in backward passes.
                        # Therefore, saving it in one process is sufficient.
                        trainer.module.save(args.saved_model_dir, iterations) 
                else: 
                    trainer.save(args.saved_model_dir, iterations)

            trainer.module.update_learning_rate() if isDDP(trainer) else trainer.update_learning_rate()

            #gc.collect()
            #torch.cuda.empty_cache()
            iterations += 1
            if iterations >= args.max_iter:
                if should_distribute(args.world_size): 
                    dist.destroy_process_group()
                flag_true = False
                sys.exit('Finish training')

            start_time = time.time()


    # if should_distribute(args.world_size): 
    #     dist.destroy_process_group()

    # sys.exit('Finish training')
