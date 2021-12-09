# python worker.py <node_failure_pr>
import socket
import sys
import random
import time
import torchvision
import torch
import numpy as np
import json


# load labels and GoogleNet
def initialize_model():
    print(">>> Initialize the model...")
    # load labels
    with open('./imagenet_label.json', 'r', encoding='utf8') as fp:
        imagenet_label = json.load(fp)

    # import model
    print(">>> Loading GoogleNet..")
    model = torchvision.models.googlenet(pretrained=True)
    model.eval()
    print(">>> Finished.")

    return model, imagenet_label


# Get full image message from manager
def get_full_message(manager_socket):
    msg = ""
    while True:
        # Get the full message
        unit_msg = manager_socket.recv(buffer_size)
        if len(unit_msg) == 0:
            manager_socket.close()
            print(">>> Disconnected with manager")
            break
        msg += unit_msg.decode("utf-8")
        if msg[-1] == '\n':
            break
    return msg


# The image message decoder
def decoder(image_message):
    decoded_msg = image_message.split(" ", 3)
    """
    decoded_msg[0] - seqnum
    decoded_msg[1] - row(pixel)
    decoded_msg[2] - column(pixel)
    decoded_msg[3] - image data
    """
    print(">>> Received a image, seqnum = " + decoded_msg[0])
    seqnum = decoded_msg[0]
    row_size = int(decoded_msg[1])
    column_size = int(decoded_msg[2])
    image = decoded_msg[3].split()
    # decode image and translate it to tensor
    image = np.array(image).astype(np.float32).reshape(3, row_size, column_size)
    image = torch.from_numpy(image)

    return seqnum, image


# Image Recognition
def image_recognition(image):
    imgs = [image]
    imgs = torch.tensor([item.detach().numpy() for item in imgs])
    print(">>> Start prediction..")
    predictions = model(imgs)
    pred_numpy = predictions[0].detach().numpy()
    pred_index = np.argmax(pred_numpy)
    pred_class = imagenet_label[str(pred_index)]
    print('>>> Prediction finished. class: ' + pred_class)

    return pred_class


# accept command line arguments
argv = sys.argv[1:]
# the probability of node failure
fail_pr = None
# the seqnum of the last received image
last_seqnum = ""
# the classification of the last received image
last_result = "apple"
# training parameters
model = None
imagenet_label = None


if len(argv) == 0:
    fail_pr = 0.0
else:
    fail_pr = float(argv[0])

buffer_size = 1024

# initialize model
model, imagenet_label = initialize_model()

# set host name and port number
host = argv[1]
port = int(argv[2])

manager_socket = socket.create_connection((host, port))

try:
    print(">>> Connected with manager: " + host + ":" + str(port))
    image_msg = ""
    while True:
        print(">>> Wait for image message from manager...")
        image_msg = get_full_message(manager_socket)
        start_time = time.time()
        # Decide if this worker fails
        if random.uniform(0, 1) < fail_pr:
            print(">>> This worker suffered one unexpected error")
            manager_socket.send("404\n".encode("utf-8"))
            manager_socket.close()
            print (">>> Disconnected with manager")
            break

        seqnum, image = decoder(image_msg)

        # Check if the new received image is duplicate
        if seqnum != last_seqnum:
            last_result = image_recognition(image)
            last_seqnum = seqnum

        while True:
            if (time.time() - start_time) < 5:
                continue
            else:
                break
        print(">>> Send the image recognition result back\n")
        print(time.time())
        result_msg = str(last_seqnum) + " " + last_result + "\n"
        manager_socket.send(result_msg.encode("utf-8"))
except Exception as e:
    print(e)
    manager_socket.close()

print(">>> Stop server")