#!/bin/bash
# Apache Axis environment setup script

export AXIS_HOME=/opt/axis
export AXIS_LIB=$AXIS_HOME/lib
export AXISCLASSPATH=$AXIS_LIB/axis.jar:$AXIS_LIB/commons-discovery.jar:$AXIS_LIB/commons-logging.jar:$AXIS_LIB/jaxrpc.jar:$AXIS_LIB/saaj.jar:$AXIS_LIB/log4j-1.2.8.jar:$AXIS_LIB/xml-apis.jar:$AXIS_LIB/xercesImpl.jar:$AXIS_LIB/wsdl4j.jar

# Add to CLASSPATH if it exists
if [ -z "$CLASSPATH" ]; then
    export CLASSPATH=$AXISCLASSPATH
else
    export CLASSPATH=$AXISCLASSPATH:$CLASSPATH
fi

echo "Axis environment variables set:"
echo "AXIS_HOME=$AXIS_HOME"
echo "AXIS_LIB=$AXIS_LIB"
echo "AXISCLASSPATH has been added to CLASSPATH"
