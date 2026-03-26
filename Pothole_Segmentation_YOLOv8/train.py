from ultralytics import YOLO


def main():
    model = YOLO("yolov8n.pt")
    model.train(
        data="data.yaml",
        epochs=30,
        imgsz=640,
        device="cpu",
        workers=0
    )


if __name__ == "__main__":
    main()
