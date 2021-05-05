import argparse
import os
import random
from datetime import datetime
import time

import numpy as np
import torch
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
from dgl.dataloading import GraphDataLoader, AsyncTransferer

from data.factory import create_dataset
from engine.train import train_one_epoch
from engine.valid import validate
from model.model import Perceiver
from utils.checkpoint_saver import CheckpointSaver
from utils.summary import update_summary


def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True  # for faster training, but not deterministic


def main(args):
    model = Perceiver(
        depth=args.depth,
        emb_dim=args.emb_dim,
        self_per_cross=args.self_per_cross,
        num_latents=args.num_latents,
        latent_dim=args.latent_dim,
    )

    seed_everything(args.seed)

    optimizer = optim.Adam(model.parameters(), 1e-3)  # TODO; LR
    scheduler = StepLR(optimizer, step_size=30, gamma=0.25)

    # dataset
    print(f"Start loading dataset...")
    start = time.time()
    train_dataset, valid_dataset, test_dataset = create_dataset(args)
    print(f"Dataset is loaded, took {time.time()-start:.2f}s")

    train_loader = GraphDataLoader(train_dataset, batch_size=args.batch_size)
    valid_loader = GraphDataLoader(valid_dataset, batch_size=args.batch_size)
    transferer = AsyncTransferer(torch.device('cuda:0'))

    exp_name = '-'.join([
        datetime.now().strftime("%Y%m%d-%H%M%S"),
        # args.model,
    ])
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output', exp_name)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    saver = CheckpointSaver(
        model=model,
        optimizer=optimizer,
        args=args,
        checkpoint_dir=output_dir,
        recovery_dir=output_dir,
        decreasing=True,
    )

    best_metric = None
    best_epoch = None
    for epoch in range(args.epochs):
        train_metric = train_one_epoch(
            epoch=epoch,
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            transferer=transferer,
        )

        eval_metric = validate(
            epoch=epoch,
            model=model,
            loader=valid_loader,
            transferer=transferer,
        )

        update_summary(
            epoch, train_metric, eval_metric, os.path.join(output_dir, 'summary.csv'),
            write_header=best_metric is None
        )
        # save proper checkpoint with eval metric
        save_metric = eval_metric['loss']
        best_metric, best_epoch = saver.save_checkpoint(epoch, metric=save_metric)

        # step
        scheduler.step()


if __name__ == "__main__":
    # TODO; make clean
    default_data_folder = os.path.join(os.path.dirname(__file__), '..', 'dataset')
    default_data_folder = os.path.abspath(default_data_folder)
    parser = argparse.ArgumentParser()

    # train
    parser.add_argument('--data', type=str, default=default_data_folder)
    parser.add_argument('-b', dest='batch_size', type=int, default=256)
    parser.add_argument('--epochs', type=int, default=100)

    # model
    parser.add_argument('--emb-dim', type=int, default=128)
    parser.add_argument('--depth', type=int, default=3)
    parser.add_argument('--self-per-cross', type=int, default=1)
    parser.add_argument('--num-latents', type=int, default=128)
    parser.add_argument('--latent-dim', type=int, default=256)

    # misc
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--seed', default=42)

    args = parser.parse_args()
    main(args)