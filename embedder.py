"""Main"""
import argparse

import torch

from dataset.video_extraction_conversion import select_frames, generate_landmarks
from network.blocks import *
from network.model import Embedder
import face_alignment

import numpy as np


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model')
    parser.add_argument('--video')
    parser.add_argument('--output')

    return parser.parse_args()


def main():
    args = parse_args()
    """Hyperparameters and config"""
    use_cuda = torch.cuda.is_available()
    device = torch.device('cuda' if use_cuda else 'cpu')
    cpu = torch.device("cpu")
    path_to_e_hat_video = args.output
    path_to_video = args.video
    T = 32
    face_aligner = face_alignment.FaceAlignment(
        face_alignment.LandmarksType._2D,
        flip_input=False,
        device='cuda' if use_cuda else 'cpu'
    )

    """Loading Embedder input"""
    print("Select frames...")
    frame_mark_video = select_frames(path_to_video, T)
    print("Generate landmarks...")
    frame_mark_video = generate_landmarks(frame_mark_video, face_aligner, size=256)
    frame_mark_video = torch.from_numpy(np.array(frame_mark_video)).type(dtype=torch.float)  # T,2,256,256,3
    frame_mark_video = frame_mark_video.permute([0, 1, 4, 2, 3]).to(device) / 255  # T,2,3,256,256
    f_lm_video = frame_mark_video.unsqueeze(0)  # 1,T,2,3,256,256

    E = Embedder(256).to(device)
    E.eval()

    """Loading from past checkpoint"""
    checkpoint = torch.load(args.model, map_location=cpu)
    E.load_state_dict(checkpoint['E_state_dict'])

    """Inference"""
    with torch.no_grad():
        # forward
        # Calculate average encoding vector for video
        f_lm = f_lm_video
        f_lm_compact = f_lm.view(-1, f_lm.shape[-4], f_lm.shape[-3], f_lm.shape[-2], f_lm.shape[-1])  # BxT,2,3,224,224
        print('Run inference...')
        e_vectors = E(f_lm_compact[:, 0, :, :, :], f_lm_compact[:, 1, :, :, :])  # BxT,512,1
        e_vectors = e_vectors.view(-1, f_lm.shape[1], 512, 1)  # B,T,512,1
        e_hat_video = e_vectors.mean(dim=1)

    print('Saving e_hat...')
    torch.save({'e_hat': e_hat_video}, path_to_e_hat_video)
    print('...Done saving')


if __name__ == '__main__':
    main()
