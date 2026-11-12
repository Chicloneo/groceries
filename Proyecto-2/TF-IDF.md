# TF-IDF en la clasificación de productos

Este documento explica cómo se usa TF-IDF en el clasificador de Proyecto 2 y
qué papel cumple dentro del flujo completo. El objetivo es sugerir la categoría
y la subcategoría de un producto a partir de su nombre.

## Contenido

1. [El problema](#el-problema)
2. [Qué es TF-IDF](#qué-es-tf-idf)
3. [Cómo se aplica en este proyecto](#cómo-se-aplica-en-este-proyecto)
4. [Entrenamiento y evaluación](#entrenamiento-y-evaluación)
5. [Clasificar productos nuevos](#clasificar-productos-nuevos)

## El problema

El clasificador se entrena con el catálogo de Proyecto 1, situado en
`../Proyecto-1/Data/productos_madrid_centro.csv`. Usa el nombre del producto
como entrada y aprende a predecir su categoría y su subcategoría.

El catálogo tiene 36.766 filas, pero muchos productos aparecen más de una vez
por estar asociados a distintos códigos postales. Antes de entrenar, el
proyecto elimina esas repeticiones y trabaja con 3.571 nombres únicos. Si un
mismo nombre tiene etiquetas distintas, conserva la combinación de categoría
y subcategoría más frecuente.

## Qué es TF-IDF

TF-IDF convierte texto en valores numéricos que un modelo puede utilizar. La
ponderación combina dos ideas:

- **Frecuencia del término (TF):** cuánto aparece un término en el texto.
- **Frecuencia inversa de documento (IDF):** cuánto ayuda ese término a
  distinguir un texto del resto del conjunto.

Por ejemplo, «leche» puede aparecer en muchos productos y, por sí sola, aportar
poca información para distinguirlos. En cambio, una palabra menos común como
«deslactosada» puede ayudar a identificar un tipo concreto de producto.

De forma simplificada, el peso de un término se expresa así:

```text
TF-IDF(término, producto) = TF(término, producto) × IDF(término)
```

En scikit-learn, el cálculo también suaviza el IDF y normaliza los vectores.
En este proyecto se suaviza el efecto de términos repetidos mediante una
frecuencia TF logarítmica.

TF-IDF no clasifica por sí solo: prepara las características de texto que luego
utiliza el modelo de clasificación.

## Cómo se aplica en este proyecto

El clasificador combina dos representaciones TF-IDF:

| Representación | Qué captura | Configuración principal |
| --- | --- | --- |
| Palabras | Términos y pares de palabras, como «aceite» y «aceite de oliva» | N-gramas de 1 a 2 palabras |
| Caracteres | Fragmentos de palabras, útiles para marcas, palabras compuestas y pequeñas variaciones | N-gramas de 3 a 5 caracteres, dentro de los límites de cada palabra |

Las dos representaciones se combinan antes de entrenar el clasificador. Se
conservan palabras como «sin» y «de», que pueden aportar información en nombres
como «sin azúcar» o «aceite de oliva». La configuración detallada se encuentra
en [`classifier.py`](src/proyecto_2/classifier.py).

La transformación se ajusta con los datos de entrenamiento y después se aplica
a los datos de prueba y a los productos nuevos. Así, el vocabulario no se
construye con información del conjunto de prueba.

## Entrenamiento y evaluación

El proyecto utiliza regresión logística para predecir la categoría y la
subcategoría. Se entrena un modelo independiente para cada tarea, y se ponderan
las clases menos representadas para que tengan más peso durante el
entrenamiento.

La partición se hace sobre nombres únicos. Se reserva aproximadamente un 20 %
para la prueba y se procura que cada subcategoría esté presente tanto en
entrenamiento como en prueba. Con `random_state=42`, el conjunto queda formado
por 2.851 productos de entrenamiento y 720 de prueba.

Resultados de esa partición:

| Tarea | Exactitud | F1 macro |
| --- | ---: | ---: |
| Categoría (24 clases) | 92,4 % | 91,2 % |
| Subcategoría (134 clases) | 85,4 % | 81,1 % |

La exactitud mide la proporción de predicciones correctas. El F1 macro calcula
el F1 de cada clase y luego promedia esos valores por igual, por lo que también
refleja el rendimiento en clases con pocos productos. Los resultados pueden
cambiar si cambia el catálogo o la partición.

## Clasificar productos nuevos

La función `train_classifier` carga los datos, prepara la partición y entrena
los modelos. Después se puede usar `predict` para clasificar nombres nuevos:

```python
from proyecto_2.classifier import train_classifier

clasificador = train_classifier()
predicciones = clasificador.predict([
    "Leche de avena sin azúcar 1 L",
    "Pintalabios mate rojo 24 h",
])

print(predicciones)
```

La predicción incluye la categoría, la subcategoría, las probabilidades
estimadas y las alternativas principales de subcategoría.

Para consultar cómo se ejecuta el proyecto, cómo se guarda el modelo y cómo
interpretar sus resultados, véase el [README de Proyecto 2](README.md).
