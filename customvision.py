"""
Prediction client for the Azure Custom Vision service
======================================================

Use this with models generated using https://customvision.ai
"""

import json
import time
from typing import Optional
import adafruit_requests as requests

VERSION = "3.0"


class CustomVisionError(Exception):
    """
    An error from the custom vision service
    """

    def __init__(self, message):
        super(CustomVisionError, self).__init__(message)
        self.message = message


class BoundingBox:
    """Bounding box that defines a region of an image.

    All required parameters must be populated in order to send to Azure.

    :param left: Required. Coordinate of the left boundary.
    :type left: float
    :param top: Required. Coordinate of the top boundary.
    :type top: float
    :param width: Required. Width.
    :type width: float
    :param height: Required. Height.
    :type height: float
    """

    def __init__(self, left: float, top: float, width: float, height: float) -> None:
        self.left = left
        self.top = top
        self.width = width
        self.height = height


class Prediction:
    """Prediction result.

    Variables are only populated by the server, and will be ignored when
    sending a request.

    :ivar probability: Probability of the tag.
    :vartype probability: float
    :ivar tag_id: Id of the predicted tag.
    :vartype tag_id: str
    :ivar tag_name: Name of the predicted tag.
    :vartype tag_name: str
    :ivar bounding_box: Bounding box of the prediction.
    :vartype bounding_box:
     ~circuitpython_customvision.prediction.models.BoundingBox
    """

    def __init__(self, probability: float, tag_id: str, tag_name: str, bounding_box: BoundingBox) -> None:
        self.probability = probability
        self.tag_id = tag_id
        self.tag_name = tag_name
        self.bounding_box = bounding_box


class ImagePrediction:
    """Result of an image prediction request.

    Variables are only populated by the server, and will be ignored when
    sending a request.

    :ivar id: Prediction Id.
    :vartype id: str
    :ivar project: Project Id.
    :vartype project: str
    :ivar iteration: Iteration Id.
    :vartype iteration: str
    :ivar created: Date this prediction was created.
    :vartype created: datetime
    :ivar predictions: List of predictions.
    :vartype predictions:
     list[~_customvision.prediction.models.Prediction]
    """

    def __init__(self, response) -> None:

        if not isinstance(response, dict):
            response = json.loads(response)

        self.prediction_id = response["id"]
        self.project = response["project"]
        self.iteration = response["iteration"]
        self.created = response["created"]
        self.predictions = []

        for pred in response["predictions"]:
            box = pred["boundingBox"]
            bounding_box = BoundingBox(left=box["left"], top=box["top"], width=box["width"], height=box["height"])
            prediction = Prediction(
                probability=pred["probability"], tag_id=pred["tagId"], tag_name=pred["tagName"], bounding_box=bounding_box
            )
            self.predictions.append(prediction)


def __run_request(url, body, headers):
    retry = 0
    r = None

    while retry < 10:
        try:
            print("Trying to send...")
            r = requests.post(url, data=body, headers=headers)

            if r.status_code != 200:
                raise CustomVisionError(r.text)
            break
        except RuntimeError as runtime_error:
            print("Could not send data, retrying after 5 seconds: ", runtime_error)
            retry = retry + 1

            if retry >= 10:
                raise

            time.sleep(0.5)
            continue

    return r


class CustomVisionPredictionClient:
    """CustomVisionPredictionClient

    :param api_key: API key.
    :type api_key: str
    :param endpoint: Supported Cognitive Services endpoints.
    :type endpoint: str
    """

    __classify_image_url_route = "customvision/v3.0/Prediction/{projectId}/classify/iterations/{publishedName}/url"
    __classify_image_route = "customvision/v3.0/Prediction/{projectId}/classify/iterations/{publishedName}/image"
    __detect_image_url_route = "customvision/v3.0/Prediction/{projectId}/classify/iterations/{publishedName}/url"
    __detect_image_route = "customvision/v3.0/Prediction/{projectId}/classify/iterations/{publishedName}/image"

    def __init__(self, api_key, endpoint):

        self.__api_key = api_key

        # build the root endpoint
        if not endpoint.lower().startswith("https://"):
            endpoint = "https://" + endpoint
        if not endpoint.endswith("/"):
            endpoint = endpoint + "/"

        self.__base_endpoint = endpoint
        self.api_version = VERSION

    def __format_endpoint(self, url_format: str, project_id: str, published_name: str, store: bool, application: Optional[str]):
        endpoint = self.__base_endpoint + url_format.format(projectId=project_id, publishedName=published_name)
        if not store:
            endpoint = endpoint + "/nostore"
        if application is not None:
            application = "?" + application
            endpoint = endpoint + application

        return endpoint

    def __process_image_url(self, route: str, project_id: str, published_name: str, url: str, store: bool, application: Optional[str]):
        endpoint = self.__format_endpoint(route, project_id, published_name, store, application)

        headers = {"Content-Type": "application/json", "Prediction-Key": self.__api_key}

        body = json.dumps({"url": url})
        result = __run_request(endpoint, body, headers)
        result_text = result.text

        return ImagePrediction(result_text)

    def __process_image(
        self, route: str, project_id: str, published_name: str, image_data: bytearray, store: bool, application: Optional[str]
    ):
        endpoint = self.__format_endpoint(route, project_id, published_name, store, application)

        headers = {"Content-Type": "application/octet-stream", "Prediction-Key": self.__api_key}

        result = __run_request(endpoint, image_data, headers)
        result_text = result.text

        return ImagePrediction(result_text)

    def __classify_image_url(self, project_id: str, published_name: str, url: str, store: bool, application: Optional[str]):
        return self.__process_image_url(self.__classify_image_url_route, project_id, published_name, url, store, application)

    def __classify_image(self, project_id: str, published_name: str, image_data: bytearray, store: bool, application: Optional[str]):
        return self.__process_image(self.__classify_image_route, project_id, published_name, image_data, store, application)

    def __detect_image_url(self, project_id: str, published_name: str, url: str, store: bool, application: Optional[str]):
        return self.__process_image_url(self.__detect_image_url_route, project_id, published_name, url, store, application)

    def __detect_image(self, project_id: str, published_name: str, image_data: bytearray, store: bool, application: Optional[str]):
        return self.__process_image(self.__detect_image_route, project_id, published_name, image_data, store, application)

    def classify_image_url(self, project_id: str, published_name: str, url: str, application: Optional[str] = None):
        """Classify an image url and saves the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param url: Url of the image.
        :type url: str
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__classify_image_url(project_id, published_name, url, True, application)

    def classify_image_url_with_no_store(self, project_id: str, published_name: str, url: str, application: Optional[str] = None):
        """Classify an image url without saving the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param url: Url of the image.
        :type url: str
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__classify_image_url(project_id, published_name, url, False, application)

    def classify_image(self, project_id: str, published_name: str, image_data: bytearray, application: Optional[str] = None):
        """Classify an image and saves the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param image_data: Binary image data. Supported formats are JPEG, GIF,
         PNG, and BMP. Supports images up to 4MB.
        :type image_data: bytearray
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__classify_image(project_id, published_name, image_data, True, application)

    def classify_image_with_no_store(self, project_id: str, published_name: str, image_data: bytearray, application: Optional[str] = None):
        """Classify an image without saving the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param image_data: Binary image data. Supported formats are JPEG, GIF,
         PNG, and BMP. Supports images up to 4MB.
        :type image_data: bytearray
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__classify_image(project_id, published_name, image_data, False, application)

    def detect_image_url(self, project_id: str, published_name: str, url: str, application: Optional[str] = None):
        """Detect objects in an image url and saves the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param url: Url of the image.
        :type url: str
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__detect_image_url(project_id, published_name, url, True, application)

    def detect_image_url_with_no_store(self, project_id: str, published_name: str, url: str, application: Optional[str] = None):
        """Detect objects in an image url without saving the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param url: Url of the image.
        :type url: str
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__detect_image_url(project_id, published_name, url, False, application)

    def detect_image(self, project_id: str, published_name: str, image_data: bytearray, application: Optional[str] = None):
        """Detect objects in an image and saves the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param image_data: Binary image data. Supported formats are JPEG, GIF,
         PNG, and BMP. Supports images up to 4MB.
        :type image_data: bytearray
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__detect_image(project_id, published_name, image_data, True, application)

    def detect_image_with_no_store(self, project_id: str, published_name: str, image_data: bytearray, application: Optional[str] = None):
        """Detect objects in an image without saving the result.

        :param project_id: The project id.
        :type project_id: str
        :param published_name: Specifies the name of the model to evaluate
         against.
        :type published_name: str
        :param image_data: Binary image data. Supported formats are JPEG, GIF,
         PNG, and BMP. Supports images up to 4MB.
        :type image_data: bytearray
        :param application: Optional. Specifies the name of application using
         the endpoint.
        :type application: str
        :return: ImagePrediction
        :rtype:
         ~circuitpython_customvision.prediction.models.ImagePrediction
        :raises:
         :class:`CustomVisionError<circuitpython.customvision.prediction.models.CustomVisionErrorException>`
        """
        return self.__detect_image(project_id, published_name, image_data, False, application)