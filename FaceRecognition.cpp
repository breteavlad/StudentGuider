#include <opencv2/opencv.hpp>
#include <opencv2/objdetect.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/face.hpp>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <vector>
#include <string>
#include <map>
#include <opencv2/core/types_c.h>
#include <unistd.h> 
#include <sys/stat.h>
#include <fcntl.h>  
#include <errno.h>  


using namespace cv;
using namespace cv::face;
using namespace std;
namespace fs = std::filesystem;


Ptr<LBPHFaceRecognizer> model; // Face recognizer model
std::vector<Mat> images;        // Training images
std::vector<int> labels;        // Labels for training images
std::vector<std::string> names; // Names corresponding to labels
int pipe_fd = -1;

bool loadFaceRecognizer();
bool trainFaceRecognizer();
bool loadTrainingData();
void detectAndDraw(Mat& img, CascadeClassifier& cascade, CascadeClassifier& nestedCascade, double scale, bool doRecognize = true);
VideoCapture initializeCapture();

void initPipe() {
    pipe_fd = open("/tmp/studentName_pipe", O_WRONLY | O_NONBLOCK);
    if (pipe_fd == -1) {
    std::cerr << "Failed to open pipe for writing: " << strerror(errno) << "\n"<<std::flush;
    } else {
        std::cerr << "Pipe opened successfully for writing\n"<<std::flush;
    }
}

void sendStudentName(const std::string& studentName) {
    static std::string lastSent;

    std::cerr<<"Function called with: "<<studentName<<std::endl<<std::flush;
    if (studentName == lastSent){
    std::cerr<<"Inside the lastSent if: "<<studentName<<std::endl<<std::flush;
     return;
    }
     lastSent = studentName;

    if (pipe_fd != -1) {
        std::string msg = studentName + "\n";
        ssize_t result= write(pipe_fd, msg.c_str(), msg.size());
       if (result == -1) {
            if (errno == EPIPE) {
                std::cerr << "No reader on pipe\n"<<std::flush;
            } else if (errno == EAGAIN || errno == EWOULDBLOCK) {
                std::cerr << "INFO: No reader currently available on pipe\n"<<std::flush;

            } else {
                std::cerr << "Write failed: " << strerror(errno) << "\n"<<std::flush;
            }
        }
    }
}


void startRecognition(CascadeClassifier& cascade, CascadeClassifier& nestedCascade, double scale) {
    if (model->empty() && !loadFaceRecognizer()) {
        std::cerr << "No trained model available. Train the recognizer first.\n"<<std::flush;
        return;
    }

    VideoCapture capture=initializeCapture();
    if (!capture.isOpened()) {
        std::cerr << "Error opening video capture\n"<<std::flush;
        return;
    }

    cout << "Face Recognition Started uuu... Press 'q' to quit\n"<<std::flush;

    Mat frame;
    while (true) {
        cout<<"Before capturing frames... "<<std::endl;
        capture >> frame;
        cout<<"After capturing frames..."<<std::endl;
        if (frame.empty()) {
            std::cerr << "Error: Blank frame\n"<<std::flush;
            break;
        }

        cout<<"Before detecting and drawing in startRecognition"<<std::endl;

        Mat frameClone = frame.clone();
        detectAndDraw(frameClone, cascade, nestedCascade, scale, true);

        char c = (char)waitKey(10);
        if (c == 'q' || c == 27) {
            break;
        }
    }

    destroyWindow("Face Recognition");
}



// Function to initialize video capture with fallback options
VideoCapture initializeCapture() {
    VideoCapture capture;
    
    // For Raspberry Pi, we need to use the named pipe approach
    std::cerr << "Setting up Raspberry Pi camera with named pipe..." << endl<<std::flush;
    
    // First, try to create the named pipe if it doesn't exist
    system("mkfifo /tmp/vidpipe 2>/dev/null || true");
    
    // Start rpicam-vid in the background if not already running
    system("pkill rpicam-vid 2>/dev/null || true"); // Kill any existing instances
    system("rpicam-vid -t 0 --width 640 --height 480 --framerate 30 --codec mjpeg --output /tmp/vidpipe &");
    
    // Wait a moment for the pipe to be ready
    sleep(2);
    
    // Try to open the pipe with OpenCV
    std::cerr << "Attempting to open video pipe: /tmp/vidpipe" << endl<<std::flush;
    
    // Try opening as a video file (pipe)
    capture.open("/tmp/vidpipe", CAP_FFMPEG);
    
    if (capture.isOpened()) {
        std::cerr << "Successfully opened Raspberry Pi camera via named pipe" << endl<<std::flush;
        return capture;
    }
    
    std::cerr << "Named pipe failed, trying standard camera access..." << std::flush;
    
    // Fallback: try standard camera indices
    for (int i = 0; i < 3; i++) {
        std::cerr << "Trying camera index: " << i << endl<<std::flush;
        capture.open(i);
        
        if (capture.isOpened()) {
            std::cerr << "Successfully opened camera index: " << i << endl<<std::flush;
            return capture;
        }
    }
    
    std::cerr << "Error: Could not open any video source" << endl<<std::flush;
    std::cerr << "Make sure rpicam-vid is available and camera is connected" << endl<<std::flush;
    return capture;
}

// Function to detect and draw faces
void detectAndDraw(Mat& img, CascadeClassifier& cascade,
    CascadeClassifier& nestedCascade,
    double scale, bool doRecognize)
{
    doRecognize=true;

    std::cerr << "detectAndDraw called" << std::endl<<std::flush; // Check if function runs
    std::vector<Rect> faces;
    Mat gray, smallImg;
    cvtColor(img, gray, COLOR_BGR2GRAY); // Convert to Gray Scale
    double fx = 1 / scale;
    // Resize the Grayscale Image 
    resize(gray, smallImg, Size(), fx, fx, INTER_LINEAR);
    equalizeHist(smallImg, smallImg);
    // Detect faces of different sizes using cascade classifier 
    cascade.detectMultiScale(smallImg, faces, 1.1,
        2, 0 | CASCADE_SCALE_IMAGE, Size(30, 30));

    // Draw circles around the faces
    for (size_t i = 0; i < faces.size(); i++)
    {
        Rect r = faces[i];
        Mat smallImgROI;
        std::vector<Rect> nestedObjects;
        Point center;
        Scalar color = Scalar(255, 0, 0); // Color for Drawing tool
        int radius;
        double aspect_ratio = (double)r.width / r.height;

        // Recognition - predict who this face belongs to
        string name = "Unknown";
        if (doRecognize && !model.empty() && !model->empty()) {
            // Extract face ROI
            Mat faceROI = smallImg(r);
			//!!TESTING resize
			resize(faceROI, faceROI, Size(100, 100));
            // Predict
            int predictedLabel = -1;
            double confidence = 0.0;
            model->predict(faceROI, predictedLabel, confidence);

            // If confidence is low enough, consider it a match
            if (confidence < 100.0 && predictedLabel >= 0 && predictedLabel < names.size()) {
                name = names[predictedLabel];
                // More confident = green, less confident = red
                color = Scalar(0, 255 - confidence * 2.55, confidence * 2.55);
            }
			sendStudentName(name);

            // Display name and confidence
            String box_text = name + " (" + std::to_string(int(confidence)) + ")";
            int pos_y = std::max(r.y - 10, 0) * scale;
            putText(img, box_text, Point(r.x * scale, pos_y),
                FONT_HERSHEY_SIMPLEX, 0.8, color, 2);
        }

        if (0.75 < aspect_ratio && aspect_ratio < 1.3)
        {
            center.x = cvRound((r.x + r.width * 0.5) * scale);
            center.y = cvRound((r.y + r.height * 0.5) * scale);
            radius = cvRound((r.width + r.height) * 0.25 * scale);
            circle(img, center, radius, color, 3, 8, 0);
        }
        else
            rectangle(img, cvPoint(cvRound(r.x * scale), cvRound(r.y * scale)),
                cvPoint(cvRound((r.x + r.width - 1) * scale),
                    cvRound((r.y + r.height - 1) * scale)), color, 3, 8, 0);

        if (nestedCascade.empty())
            continue;
        smallImgROI = smallImg(r);
        // Detection of eyes in the input image
        nestedCascade.detectMultiScale(smallImgROI, nestedObjects, 1.1, 2,
            0 | CASCADE_SCALE_IMAGE, Size(30, 30));
            std::cerr<<"The faces: "<<faces.size()<<endl<<std::flush;
        // Draw circles around eyes
        for (size_t j = 0; j < nestedObjects.size(); j++)
        {
            Rect nr = nestedObjects[j];
            center.x = cvRound((r.x + nr.x + nr.width * 0.5) * scale);
            center.y = cvRound((r.y + nr.y + nr.height * 0.5) * scale);
            radius = cvRound((nr.width + nr.height) * 0.25 * scale);
            circle(img, center, radius, color, 3, 8, 0);
        }
    }
    
    // Show Processed Image with detected faces
    imshow("Face Recognition", img);
}

void collectFaceSamples(CascadeClassifier& cascade, int label, const string& name) {
    VideoCapture capture=initializeCapture();
    if (!capture.isOpened()) {
        cerr << "Error opening video capture\n";
        return;
    }

    Mat frame, face;
    string folderPath = "faces/" + name;
    fs::create_directories(folderPath);

    int sampleCount = 0;
    const int MAX_SAMPLES = 20;

    std::cerr << "Collecting face samples for " << name << ". Press 's' to save a sample, 'q' to quit (or wait for samples to auto-save).\n"<<std::flush;

    while (sampleCount < MAX_SAMPLES) {
        capture >> frame;
        if (frame.empty()) {
            cerr << "Error: Blank frame\n";
            continue;
        }

        Mat gray;
        cvtColor(frame, gray, COLOR_BGR2GRAY);
        equalizeHist(gray, gray);

        vector<Rect> faces;
        cascade.detectMultiScale(gray, faces, 1.1, 3, 0, Size(100, 100));

        if (!faces.empty()) {
            Rect largestFace = faces[0];
            for (const auto& r : faces) {
                if (r.area() > largestFace.area()) {
                    largestFace = r;
                }
            }

            Mat faceROI = gray(largestFace);
            resize(faceROI, faceROI, Size(100, 100));

            string filename = folderPath + "/sample_" + to_string(sampleCount) + ".jpg";
            imwrite(filename, faceROI);
        std::cerr << "Saved " << filename << endl<<std::flush;

            sampleCount++;
            waitKey(500); // wait between frames
        }

        // Show current frame with face detection
        Mat displayFrame = frame.clone();
        vector<Rect> displayFaces;
        cascade.detectMultiScale(gray, displayFaces, 1.1, 3, 0, Size(100, 100));
        for (const auto& r : displayFaces) {
            rectangle(displayFrame, r, Scalar(0, 255, 0), 2);
        }
        imshow("Collecting Samples", displayFrame);

        char c = (char)waitKey(10);
        if (c == 'q' || c == 27) {
            break;
        }
    }

    destroyWindow("Collecting Samples");
    std::cerr << "Collected " << sampleCount << " samples for " << name << endl<<std::flush;
}

// Function to load training data from faces directory
bool loadTrainingData() {
    images.clear();
    labels.clear();
    names.clear();

    if (!fs::exists("faces")) {
        std::cerr << "Faces directory not found. Create it first.\n"<<std::flush;
        return false;
    }

    int label = 0;
    map<string, int> nameToLabel;

    // Load existing labels from file if it exists
    ifstream labelFile("faces/labels.txt");
    if (labelFile.is_open()) {
        string name;
        int lbl;
        while (labelFile >> name >> lbl) {
            nameToLabel[name] = lbl;
            while (names.size() <= lbl) {
                names.push_back("");
            }
            names[lbl] = name;
        }
        labelFile.close();
        
        // Update label counter to avoid conflicts
        if (!names.empty()) {
            label = names.size();
        }
    }

    // Iterate through faces directory
    for (const auto& entry : fs::directory_iterator("faces")) {
        if (entry.is_directory()) {
            string name = entry.path().filename().string();

            // Assign a label if this person doesn't have one yet
            if (nameToLabel.find(name) == nameToLabel.end()) {
                nameToLabel[name] = label;
                if (names.size() <= label) {
                    names.resize(label + 1);
                }
                names[label] = name;
                label++;
            }

            int personLabel = nameToLabel[name];

            // Load all face samples for this person
            for (const auto& sample : fs::directory_iterator(entry.path())) {
                if (sample.path().extension() == ".jpg" || sample.path().extension() == ".png") {
                    Mat img = imread(sample.path().string(), IMREAD_GRAYSCALE);
                    if (!img.empty()) {
                        // Resize to ensure consistent size
                        resize(img, img, Size(100, 100));
                        images.push_back(img);
                        labels.push_back(personLabel);
                    }
                }
            }
        }
    }

    // Save labels to file (FIXED: was saving to wrong path)
    ofstream outLabelFile("faces/labels.txt");
    if (outLabelFile.is_open()) {
        for (size_t i = 0; i < names.size(); i++) {
            if (!names[i].empty()) {
                outLabelFile << names[i] << " " << i << endl;
            }
        }
        outLabelFile.close();
    }

    std::cerr << "Loaded " << images.size() << " images for " << names.size() << " people\n"<<std::flush;

    return !images.empty();
}

// Function to train the face recognizer
bool trainFaceRecognizer() {
    if (images.empty() || labels.empty()) {
        cerr << "No training data available\n";
        return false;
    }

    // Create and train the LBPH Face Recognizer
    model = LBPHFaceRecognizer::create();
    model->train(images, labels);

    std::cerr << "Face recognizer trained successfully\n"<<std::flush;

    // Save the model
    model->save("faces/face_model.yml");
    std::cerr << "Model saved to faces/face_model.yml\n"<<std::flush;

    return true;
}

// Function to load a trained model if it exists
bool loadFaceRecognizer() {
    model = LBPHFaceRecognizer::create();
    try {
        model->read("faces/face_model.yml");
        std::cerr << "Loaded trained model from faces/face_model.yml\n"<<std::flush;
        return true;
    }
    catch (const cv::Exception& e) {
        std::cerr << "Error loading face model: " << e.what() << endl<<std::flush;
        return false;
    }
}

int main(int argc, const char** argv) {
    std::cerr << "Face Recognition System" << endl<<std::flush;
    
	
	struct stat st;
	
	if (stat("/tmp/studentName_pipe", &st) != 0) {
    mkfifo("/tmp/studentName_pipe", 0666);
}

initPipe();
    // Load cascades - try different possible paths
    CascadeClassifier cascade, nestedCascade;
    double scale = 1;

    vector<string> faceCascadePaths = {
        "/usr/share/opencv4/haarcascades/haarcascade_frontalface_alt.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_alt.xml",
        "haarcascade_frontalface_alt.xml"
    };

    vector<string> eyeCascadePaths = {
        "/usr/share/opencv4/haarcascades/haarcascade_eye_tree_eyeglasses.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_eye_tree_eyeglasses.xml",
        "haarcascade_eye_tree_eyeglasses.xml"
    };

    bool faceLoaded = false, eyeLoaded = false;

    for (const string& path : faceCascadePaths) {
        if (cascade.load(path)) {
            cout << "Loaded face cascade from: " << path << endl;
            faceLoaded = true;
            break;
        }
    }

    for (const string& path : eyeCascadePaths) {
        if (nestedCascade.load(path)) {
            cout << "Loaded eye cascade from: " << path << endl;
            eyeLoaded = true;
            break;
        }
    }

    if (!faceLoaded) {
        cerr << "ERROR: Could not load frontal face cascade from any path\n";
        return -1;
    }

    if (!eyeLoaded) {
        cerr << "WARNING: Could not load eye cascade - eye detection disabled\n";
    }

    // Create faces directory if it doesn't exist
    fs::create_directories("faces");

    // Load existing training data and model if available
    loadTrainingData();
    loadFaceRecognizer();
	
	   // Non-interactive mode
    if (argc > 1 && string(argv[1]) == "auto") {
        cout << "=== DETECTED AUTO MODE - GOING TO startRecognition() ===" << endl;
        startRecognition(cascade, nestedCascade, scale);
        return 0;
    }
 cout << "=== ENTERING MAIN PROCESSING LOOP ===" << endl;
    // Main menu
    while (true) {
        cout << "\nFace Recognition System\n";
        cout << "1. Add new person\n";
        cout << "2. Train recognizer\n";
        cout << "3. Start recognition\n";
        cout << "4. Exit\n";
        cout << "Choose an option: ";

        int choice;
        cin >> choice;

        switch (choice) {
        case 1: {
            cin.ignore();
            cout << "Enter person's name: ";
            string name;
            getline(cin, name);

            int newLabel = names.size();
            collectFaceSamples(cascade, newLabel, name);

            // Reload training data
            loadTrainingData();
            break;
        }
        case 2: {
            if (loadTrainingData()) {
                trainFaceRecognizer();
            }
            else {
                cout << "No training data available. Add faces first.\n";
            }
            break;
        }
        case 3: {
            // Make sure we have a trained model
            cout<<"Inside case 3 !!"<<std::endl;
            if (model.empty() || model->empty()) {
                if (!loadFaceRecognizer()) {
                    cout << "No trained model available. Train the recognizer first.\n";
                    break;
                }
            }

           startRecognition(cascade,nestedCascade,scale);
            break;
        }
        case 4:
            cout << "Exiting...\n";
            return 0;
        default:
            cout << "Invalid option. Try again.\n";
        }
    }

    return 0;
}