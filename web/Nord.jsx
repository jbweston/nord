/*
 Copyright 2018 Joseph Weston

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
import React from 'react' ;
import AnimateHeight from 'react-animate-height'
import Spinner from 'react-spinkit'
import {
  ComposableMap,
  ZoomableGroup,
  Geographies,
  Geography,
} from "react-simple-maps"

import 'normalize.css/normalize.css'
import './static/styles.css'

// Import licence for GEOJSON so as to include it into the webpack output.
// This is necessary to avoid violating the license terms.
import './static/LICENSE'
import World from './static/world.geo.json'


const VPN = Object.freeze({
  disconnected:1,
  connecting:2,
  connected:3,
  disconnecting: 4,
  error: 5,
}) ;

class Nord extends React.Component {

  constructor(props) {
    super(props) ;
    this.state = {
        enabled: false,
        loading: true,
        status: VPN.disconnected,
        country: null,
        host: null,
        viewportWidth: null,
    } ;
    this.connection = null


    this.connect = this.connect.bind(this) ;
    this.updateDimensions = this.updateDimensions.bind(this) ;
    this.disconnect = this.disconnect.bind(this) ;
    this.handleData = this.handleData.bind(this) ;
  }

  updateDimensions() {
    this.setState({
      viewportWidth: Math.max(document.documentElement.clientWidth,
                              window.innerWidth || 0)
    }) ;
  }

  componentWillMount() {
    this.updateDimensions() ;
  }

  componentWillUnmount() {
    window.removeEventListener("resize", this.updateDimensions) ;
  }

  componentDidMount() {
    const upstream = location.hostname+(location.port ? ':'+location.port : '')
    window.addEventListener("resize", this.updateDimensions) ;
    this.setState({enabled: false, loading: true})
    this.connection = new WebSocket('ws://'+upstream+'/api') ;
    this.connection.onopen = () =>
      this.setState({enabled: true, loading: false}) ;
    this.connection.onerror = () =>
      this.setState({enabled: false, loading: false}) ;
    this.connection.onclose = () =>
      this.setState({enabled: false, loading: false}) ;
    this.connection.onmessage = this.handleData ;
  }

  handleData(msg) {
    msg = JSON.parse(msg.data)
    switch(msg.state) {
      case "connected":
        this.setState({
            status: VPN.connected,
            host: msg.host
        }) ;
        break ;
      case "disconnected":
        this.setState({
            status: VPN.disconnected
        }) ;
        break ;
      case "connecting":
        this.setState({
            status: VPN.connecting,
            country: msg.country,
            host: null,
        }) ;
        break ;
      case "disconnecting":
        this.setState({
            status: VPN.disconnecting,
        }) ;
        break ;
      case "error":
        this.setState({
            status: VPN.error,
            error_message: msg.message
        }) ;
        break ;
    }
  }

  connect(geography) {
    const country_info = geography.properties ;
//    this.setState({
//        status: VPN.connecting,
//        country: country_info.NAME,
//        host: null,
//    }) ;

    this.connection.send(JSON.stringify({
      method: 'connect',
      country: country_info.ISO_A2
    })) ;
  }

  disconnect() {
//    this.setState((prev) => ({ ...prev, status: VPN.disconnecting })) ;

    this.connection.send(JSON.stringify({
      method: 'disconnect'
    })) ;
  }

  render() {
    return (
      <div id="grid">
        <Title className="full-width"/>
        <section className="clip">
          <VPNStatus connection={ this.state }
                     onDisconnect={ this.disconnect }
                     className="full-width overlap"/>
          <WorldMap onClick={ this.connect }
                    viewportWidth={ this.state.viewportWidth }/>
        </section>
      </div>
    ) ;
  }

}


const Title = (props) => {
  return (
    <section id="title" className={props.className}>
    <h1 className="no-margin">Nord</h1>
    </section>
  ) ;
} ;


const ConnectionSpinner = () => {
  return (
    <div>
      <div className="connection-spinner">
        <Spinner name="double-bounce" fadeIn="none" />
      </div>
    </div>
  ) ;
} ;

const DisconnectButton = (props) => {
  const onClick = props.connected ? props.onDisconnect : null ;
  const content = props.connected ? "Disconnect" : <ConnectionSpinner/> ;
  return (
    <div className="disconnect-button-wrapper">
      <button className="disconnect-button red" onClick={ onClick }>
        { content }
      </button>
  </div>
  ) ;
} ;

const VPNStatus = (props) => {
  const connection = props.connection ;

  var color = "" ;
  var content = null

  switch(connection.status) {
    case VPN.connecting:
      color = "yellow" ;
      content = <div>
                  Connecting to servers in <b>{ connection.country }</b>
                  <ConnectionSpinner/>
             </div>;
      break ;
    case VPN.connected:
    case VPN.disconnecting:
    case VPN.disconnected:
      color = "green" ;
      content = <div>
                  Connected to <b>{ connection.host }</b>
                  <DisconnectButton
                    connected={ connection.status == VPN.connected }
                    onDisconnect={ props.onDisconnect }/>
               </div> ;
      break ;
    case VPN.error:
      color = "red" ;
      content = <div>Error on backend: {connection.error_message}</div> ;
  }

  if (!connection.enabled && !connection.loading) {
    color = "red" ;
    content = <div>Lost connection to backend</div> ;
  }

  return (
      <AnimateHeight
          className={props.className}
          duration={ 500 }
          height={ connection.status == VPN.disconnected ? '0' : 'auto'}>
          <div className={"padded " + color}>
            {content}
          </div>
      </AnimateHeight>
  ) ;
} ;


const WorldMap = (props) => {

  var zoom = 7 ;
  var center = [ 5, 65 ] ;
  if (props.viewportWidth > 500) {
    zoom = 4 ;
    center = [5, 50]
  }
  if (props.viewportWidth > 1000) {
    zoom = 2 ;
  }


  const default_map_style = {
    fill: "#ECEFF1",
    stroke: "#607D8B",
    strokeWidth: 0.75,
    outline: "none",
  } ;
  const map_container_style = {
    width: "100%",
    height: "100%",
  } ;
  const map_style = {
    default: default_map_style,
    hover: { ...default_map_style, fill: "#CFD8DC" },
    pressed: { ...default_map_style, fill: "#CFD8DC" },
  } ;

  return (
    <ComposableMap style={ map_container_style }>
      <ZoomableGroup zoom={ zoom } center={ center }>
        <Geographies geography={ World }>
          {(geographies, projection) => geographies.map(geography => (
            <Geography
              key={ geography.id }
              geography={ geography }
              projection={ projection }
              style={ map_style }
              onClick={ props.onClick }
              />
          ))}
        </Geographies>
      </ZoomableGroup>
    </ComposableMap>
  ) ;
} ;


export default Nord ;
