import os
import time

import cv2
import joblib
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from ultralytics import YOLO

load_dotenv()


def load_models():
    start_time = time.time()
    if os.environ.get("USE_PY_OPENSHOWVAR") == "0":
        mlp_model_path = os.path.join("models", "mlp_color_classifier.joblib")
        yolo_classification_model = YOLO(os.path.join("models", "CrabBelly.pt"))
        yolo_counting_model = YOLO(os.path.join("models", "CountingBest.pt"))
    else:
        base_model_dir = os.path.join(
            "D:",
            "RobotCommunication",
            "PythonCommunication",
            "CodesForLLM",
            "CodesForLLM",
            "MPOmodels",
        )

        mlp_model_path = os.path.join(base_model_dir, "mlp_color_classifier.joblib")
        yolo_classification_model = YOLO(os.path.join(base_model_dir, "CrabBelly.pt"))
        yolo_counting_model = YOLO(os.path.join(base_model_dir, "CountingBest.pt"))

    model_bundle = joblib.load(mlp_model_path)
    pipeline = model_bundle["pipeline"]
    mlp_classifier = model_bundle["classifier"]
    elapsed = time.time() - start_time
    print(f"[Timing] Model loading took {elapsed:.4f}s")
    return (
        yolo_classification_model,
        yolo_counting_model,
        pipeline,
        mlp_classifier,
    )


# === Color Feature Extraction ===
t00 = time.time()


def extract_color_features_from_image(image):
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist_hue = cv2.calcHist([hsv_image], [0], None, [256], [0, 256]).flatten()
    hist_saturation = cv2.calcHist([hsv_image], [1], None, [256], [0, 256]).flatten()
    hist_value = cv2.calcHist([hsv_image], [2], None, [256], [0, 256]).flatten()
    return np.concatenate((hist_hue, hist_saturation, hist_value))


t11 = time.time()


# === Process Image ===
def process_image(image_path):
    # load models
    yolo_classification_model, yolo_counting_model, pipeline, mlp_classifier = (
        load_models()
    )
    print(f"\n[INFO] Processing: {os.path.basename(image_path)}")
    total_start = time.time()

    # Step 1: Read
    t0 = time.time()
    image = cv2.imread(image_path)
    original_image = image.copy()
    t1 = time.time()
    if image is None:
        print("❌ Error: Could not read image.")
        return

    # Step 1.5: Get CrabBelly size BEFORE resize
    classification_result = yolo_classification_model.predict(
        image, verbose=False, device="cuda"
    )[0]
    found_belly = False
    carapace_condition = "Unknown"
    carapace_width_cm = 0

    if classification_result.boxes is not None:
        for box in classification_result.boxes:
            cls_id = int(box.cls[0])
            if cls_id == 0:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                width_px = x2 - x1
                height_px = y2 - y1
                width_cm = width_px / 63
                height_cm = height_px / 63
                carapace_width_cm = width_cm
                print(
                    f"📏 Carapace (CrabBelly) — Width: {width_cm:.2f} cm, Height: {height_cm:.2f} cm"
                )
                found_belly = True

                # Draw box and text on image
                # cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 255), 3)
                # label = f"{width_cm:.1f}cm x {height_cm:.1f}cm"
                # cv2.putText(image, label, (x1, y1 - 15), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                # cv2.imshow("Crab Belly with Width", image)
                # cv2.waitKey(0)
                # cv2.destroyAllWindows()
                break
    if not found_belly:
        print("⚠️ No 'CrabBelly' bounding box found.")

    # Step 2: Resize
    image = cv2.resize(image, (640, 640))
    t2 = time.time()

    # Step 3: YOLO Classification
    results_classification = classification_result
    t3 = time.time()

    # Step 4: MLP Classification
    t4 = time.time()
    for box in results_classification.boxes:
        cls_id = int(box.cls[0])
        confidence = box.conf[0]
        if cls_id == 0 and confidence > 0.7:
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Use original image for crop
            cropped = original_image[y1:y2, x1:x2]
            if cropped.size == 0:
                continue

            cropped = cv2.resize(cropped, (640, 640))

            t5 = time.time()
            features = extract_color_features_from_image(cropped).reshape(1, -1)
            features_transformed = pipeline.transform(features)
            prediction = mlp_classifier.predict(features_transformed)
            carapace_condition = prediction[0]
            t6 = time.time()

            print(
                f"[Classification] Class ID: {cls_id}, Prediction: {prediction[0]}, Confidence: {confidence:.2f}"
            )
            break
    else:
        print("[INFO] No classification target detected.")
        t6 = t5 = time.time()

    # Step 5: YOLO Counting with Claw Correction
    t7 = time.time()
    results_counting = yolo_counting_model.predict(
        source=image_path,
        conf=0.7,
        save=False,
        stream=True,
        verbose=False,
        device="cuda",
    )
    t8 = time.time()

    num_legs = 0
    num_claws = 0

    for result in results_counting:
        boxes = result.boxes
        names = result.names
        image_width = original_image.shape[1]

        cls_tensor = boxes.cls.clone().cpu()
        xyxy_tensor = boxes.xyxy.cpu()
        corrected_cls = cls_tensor.clone()

        clawL_indices, clawR_indices = [], []
        for i in range(len(cls_tensor)):
            class_id = int(cls_tensor[i])
            class_name = names[class_id]
            x1, y1, x2, y2 = xyxy_tensor[i].numpy()
            center_x = (x1 + x2) / 2
            if class_name == "ClawL":
                clawL_indices.append((i, center_x))
            elif class_name == "ClawR":
                clawR_indices.append((i, center_x))

        if len(clawL_indices) > 1:
            for idx, cx in clawL_indices:
                if cx < image_width / 2:
                    corrected_cls[idx] = names.index("ClawR")
        if len(clawR_indices) > 1:
            for idx, cx in clawR_indices:
                if cx > image_width / 2:
                    corrected_cls[idx] = names.index("ClawL")

        abdomen_count = sum(
            1 for i, c in enumerate(corrected_cls) if names[int(c)] == "Abdomen"
        )
        claw_left_count = sum(
            1 for i, c in enumerate(corrected_cls) if names[int(c)] == "ClawL"
        )
        claw_right_count = sum(
            1 for i, c in enumerate(corrected_cls) if names[int(c)] == "ClawR"
        )
        joint_count = sum(
            1 for i, c in enumerate(corrected_cls) if names[int(c)] == "Joint"
        )

        max_claws = 2 * abdomen_count
        num_claws = min(claw_left_count + claw_right_count, max_claws)
        num_legs = max(0, 8 - joint_count)

        print(
            f"[Counting] Abdomen: {abdomen_count}, Claws (L+R): {num_claws}, Legs: {num_legs}"
        )

    # Step 6: Determine Quality
    quality = "Unknown"
    if (
        num_legs == 8
        and num_claws == 2
        and carapace_condition == "Soft"
        and carapace_width_cm > 10.5
    ):
        quality = "Premium"
    elif (
        num_legs == 8
        and num_claws == 2
        and carapace_condition == "Hard"
        and carapace_width_cm > 10.5
    ):
        quality = "Grade A"
    elif num_legs == 8 and num_claws == 2 and 9 <= carapace_width_cm < 10.5:
        quality = "Grade B"
    elif num_legs == 8 and num_claws == 2 and carapace_width_cm < 9:
        quality = "Grade C"
    elif num_legs < 8 or num_claws < 2:
        quality = "Meat use"

    print("\n=== Final Result ===")

    total_end = time.time()

    # Timing Summary
    print("\n=== Timing Breakdown ===")
    print(f"Image HSV:               {t11 - t00:.4f}s")
    print(f"Image Read:               {t1 - t0:.4f}s")
    print(f"Image Resize:             {t2 - t1:.4f}s")
    print(f"YOLO Classification:      {t3 - t2:.4f}s")
    print(f"MLP Preprocess + Predict: {t6 - t5:.4f}s")
    print(f"YOLO Counting:            {t8 - t7:.4f}s")
    print(f"Total Pipeline Time:      {total_end - total_start:.4f}s\n")

    # === Loop for User to Try Multiple Images ===
    # while True:
    # image_path = input("Enter image path (or 'q' to quit): ").strip()
    # if image_path.lower() == "q":
    #     print("👋 Exiting...")
    #     break
    # if not os.path.isfile(image_path):
    #     print("❌ Invalid path. Try again.")
    #     continue
    # process_image(image_path)
    return f"Legs: {num_legs}, Claws: {num_claws}, Carapace Width: {carapace_width_cm:.2f} cm, Condition: {carapace_condition}, Quality: {quality}"


# process_image("MAY2024_Crab001_ventral_1_JPG.rf.6374659fc0dd947596fbc2c4fee442ab.jpg")
