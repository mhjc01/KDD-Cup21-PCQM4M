import torch
import torch.nn.functional as F
from tqdm import tqdm

from utils.metrics import AverageMeter


def train_one_epoch(
        epoch,
        model,
        loader,
        optimizer,
        transferer,
):
    model.train()
    last_batch = len(loader) - 1

    loss_m = AverageMeter()
    pbar = tqdm(loader, ascii=True)
    for i, (graph, labels) in enumerate(pbar):
        atom_input = graph.ndata['feat']
        atom_input_gpu = transferer.async_copy(atom_input, torch.device('cuda:0'))
        bond_input = graph.edata['feat']
        bond_input_gpu = transferer.async_copy(bond_input, torch.device('cuda:0'))
        # Forward
        outputs = model(graph, atom_input_gpu.wait(), bond_input_gpu.wait())

        # Compute loss
        loss = F.l1_loss(outputs, labels.cuda())

        # Backward
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        loss_m.update(loss.item(), graph.batch_size)

        if i % 10 == 0 or i == last_batch:
            pbar.set_description(f"Epoch {epoch:02d}, Loss {loss_m.avg:.5f}")

    return {
        'loss': loss_m.avg
    }
