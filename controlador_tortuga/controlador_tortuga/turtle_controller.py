"""Control sencillo de TurtleSim para la práctica de ROS 2."""

import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from turtlesim_msgs.msg import Pose

from controlador_tortuga_interfaces.action import FollowTrajectory
from controlador_tortuga_interfaces.srv import SetMode


class ControladorTortuga(Node):
    """Nodo que controla los modos manual, círculo y trayectoria."""

    def __init__(self):
        # Profesor, __init__() no se usa por ser algo propio de la IA, sino porque
        # necesito inicializar la clase padre Node y preparar las funciones que
        # ROS 2 ya tiene integradas. Así se pueden crear tópicos, servicios y
        # acciones antes de que el executor comience a recibir datos.
        super().__init__('turtle_controller')

        # 1. Datos que el programa necesita recordar.
        self.posicion = None
        self.modo = 'manual'
        self.horario = True

        # Este grupo permite atender varias comunicaciones de ROS 2.
        self.grupo_llamadas = ReentrantCallbackGroup()

        # 2. Salidas: velocidad de la tortuga y modo actual.
        self.publicador_velocidad = self.create_publisher(
            Twist, '/turtle1/cmd_vel', 10)
        self.publicador_modo = self.create_publisher(String, '/current_mode', 10)

        # 3. Entrada: posición actual publicada por TurtleSim.
        self.create_subscription(
            Pose, '/turtle1/pose', self.guardar_posicion, 10,
            callback_group=self.grupo_llamadas)

        # 4. Servicio para escoger manual o círculo.
        self.create_service(
            SetMode, '/set_mode', self.cambiar_modo,
            callback_group=self.grupo_llamadas)

        # 5. Acción para recorrer tres puntos y permitir cancelación.
        self.trayectoria = ActionServer(
            self,
            FollowTrajectory,
            '/follow_trajectory',
            self.seguir_trayectoria,
            goal_callback=self.revisar_puntos,
            cancel_callback=self.aceptar_cancelacion,
            callback_group=self.grupo_llamadas,
        )

        # 6. Cada 0.1 segundos se publica el modo y se revisa el círculo.
        self.create_timer(0.1, self.actualizar, callback_group=self.grupo_llamadas)
        self.get_logger().info('Controlador listo')

    def guardar_posicion(self, posicion):
        """Guarda la posición que publica turtlesim."""
        self.posicion = posicion

    def actualizar(self):
        """Publica el modo y mueve la tortuga si el modo es círculo."""
        self.publicador_modo.publish(String(data=self.modo))

        if self.modo == 'circulo':
            orden = Twist()
            # linear.x hace avanzar y angular.z hace girar.
            orden.linear.x = 1.0
            orden.angular.z = -0.8 if self.horario else 0.8
            self.publicador_velocidad.publish(orden)

    def detener(self):
        """Envía velocidad cero: la tortuga se detiene."""
        self.publicador_velocidad.publish(Twist())

    def cambiar_modo(self, solicitud, respuesta):
        """Responde al servicio /set_mode."""
        # lower pasa el texto a minúsculas y strip elimina espacios.
        modo_solicitado = solicitud.modo.lower().strip()

        if modo_solicitado == 'manual':
            self.modo = 'manual'
            self.detener()
            respuesta.exito = True
            respuesta.mensaje = 'Modo manual activado'
        elif modo_solicitado == 'circulo':
            self.modo = 'circulo'
            self.horario = solicitud.horario
            respuesta.exito = True
            respuesta.mensaje = 'Círculo activado'
        else:
            respuesta.exito = False
            respuesta.mensaje = 'Usa manual o circulo'

        return respuesta

    def revisar_puntos(self, meta):
        """Solo acepta la acción si recibe exactamente tres puntos."""
        if len(meta.puntos_x) == 3 and len(meta.puntos_y) == 3:
            return GoalResponse.ACCEPT
        return GoalResponse.REJECT

    def aceptar_cancelacion(self, manejador_meta):
        """Permite que el usuario cancele una trayectoria."""
        return CancelResponse.ACCEPT

    def error_angulo(self, angulo_deseado, angulo_actual):
        """Devuelve el giro corto necesario para mirar hacia el objetivo."""
        error = angulo_deseado - angulo_actual
        return math.atan2(math.sin(error), math.cos(error))

    def ir_al_punto(self, x, y, numero_punto, manejador_meta):
        """Mueve la tortuga hasta un punto. Devuelve False si se cancela."""
        # Repite el control hasta llegar al punto, cancelar o cerrar ROS 2.
        while rclpy.ok():
            # Si el usuario cancela la acción, informa que el movimiento debe detenerse.
            if manejador_meta.is_cancel_requested:
                return False

            # Sin una posición actual no se puede calcular hacia dónde avanzar.
            if self.posicion is None:
                time.sleep(0.1)
                continue

            # Calcula cuánto falta en x y en y desde la posición actual.
            diferencia_x = x - self.posicion.x
            diferencia_y = y - self.posicion.y
            # Calcula la distancia recta que falta para llegar al punto.
            distancia = math.hypot(diferencia_x, diferencia_y)

            # Envía el punto actual y la distancia restante mientras avanza.
            retroalimentacion = FollowTrajectory.Feedback()
            retroalimentacion.punto_actual = numero_punto
            retroalimentacion.distancia_restante = distancia
            manejador_meta.publish_feedback(retroalimentacion)

            # Si ya está cerca del punto, se detiene y avisa que llegó.
            if distancia < 0.15:
                self.detener()
                return True

            # Calcula hacia dónde debe mirar y cuánto debe girar.
            angulo_deseado = math.atan2(diferencia_y, diferencia_x)
            giro = self.error_angulo(angulo_deseado, self.posicion.theta)

            orden = Twist()
            # Publica el giro y el avance necesarios para llegar al punto.
            orden.angular.z = 4.0 * giro
            orden.linear.x = min(1.2, 1.5 * distancia)
            # Si todavía mira muy lejos del objetivo, primero gira sin avanzar.
            if abs(giro) > 0.8:
                orden.linear.x = 0.0
            self.publicador_velocidad.publish(orden)
            # Espera un instante antes de revisar la posición nueva.
            time.sleep(0.1)

        return False

    def seguir_trayectoria(self, manejador_meta):
        """Ejecuta la acción: visita los tres puntos uno por uno."""
        self.modo = 'trayectoria'
        resultado = FollowTrajectory.Result()

        for numero in range(3):
            x = manejador_meta.request.puntos_x[numero]
            y = manejador_meta.request.puntos_y[numero]

            if not self.ir_al_punto(x, y, numero + 1, manejador_meta):
                self.detener()
                self.modo = 'manual'
                manejador_meta.canceled()
                resultado.exito = False
                resultado.mensaje = 'Trayectoria cancelada'
                return resultado

        self.detener()
        self.modo = 'manual'
        manejador_meta.succeed()
        resultado.exito = True
        resultado.mensaje = 'Trayectoria completada'
        return resultado


def principal(argumentos=None):
    # Inicia ROS 2 antes de crear cualquier nodo.
    rclpy.init(args=argumentos)
    # Crea el controlador y ejecuta su __init__ para preparar las comunicaciones.
    controlador = ControladorTortuga()
    # El executor escucha los mensajes y llama las funciones correspondientes.
    ejecutor = MultiThreadedExecutor()
    ejecutor.add_node(controlador)

    try:
        # Mantiene el programa activo mientras recibe tópicos, servicios y acciones.
        ejecutor.spin()
    except KeyboardInterrupt:
        # Ctrl+C es una forma normal de detener el programa.
        pass
    finally:
        # Estas instrucciones se ejecutan siempre para cerrar ROS 2 correctamente.
        ejecutor.shutdown()
        controlador.destroy_node()
        rclpy.shutdown()
